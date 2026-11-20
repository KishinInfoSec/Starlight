from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import DatabaseError
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views import generic

import logging

from .models import Attempt, AttemptAnswer, Quiz, Topic

logger = logging.getLogger(__name__)


def published_quizzes():
    return Quiz.objects.filter(pub_date__lte=timezone.now())


class TopicListView(generic.ListView):
    template_name = "quizzes/topic_list.html"
    context_object_name = "topics"

    def get_queryset(self):
        """Topics with at least one published quiz."""
        return Topic.objects.annotate(
            quiz_count=Count("quizzes", filter=Q(quizzes__pub_date__lte=timezone.now()))
        ).filter(quiz_count__gt=0)


class TopicDetailView(generic.DetailView):
    model = Topic
    template_name = "quizzes/topic_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["quizzes"] = published_quizzes().filter(topic=self.object)
        return context


class QuizDetailView(generic.DetailView):
    template_name = "quizzes/quiz_detail.html"

    def get_queryset(self):
        """Excludes any quizzes that aren't published yet."""
        return published_quizzes().select_related("topic").annotate(question_count=Count("questions"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            mine = Attempt.objects.completed().filter(user=self.request.user, quiz=self.object)
            context["attempt_count"] = mine.count()
            context["best_attempt"] = mine.order_by("-score", "-created").first()
        return context


@login_required
def take(request, slug):
    quiz = get_object_or_404(published_quizzes(), slug=slug)
    questions = list(quiz.questions.prefetch_related("options"))
    if request.method != "POST":
        return render(request, "quizzes/take.html", {"quiz": quiz, "questions": questions})
    if not questions:
        return HttpResponseRedirect(reverse("quizzes:detail", args=(quiz.slug,)))

    answers = []
    for question in questions:
        options = {option.pk: option for option in question.options.all()}
        raw = request.POST.get(f"question-{question.pk}", "")
        try:
            selected = options.get(int(raw))
        except ValueError:
            selected = None
        answers.append((question, selected, bool(selected and selected.is_correct)))

    # No transaction (some database backends have no transactions): write the attempt as incomplete, then its
    # answers, then flip `completed` LAST. Anything that fails earlier leaves an
    # incomplete attempt that no view lists, scores or opens.
    attempt = None
    try:
        attempt = Attempt.objects.create(
            user=request.user, quiz=quiz,
            score=sum(1 for _, _, ok in answers if ok), total=len(answers),
        )
        AttemptAnswer.objects.bulk_create(
            AttemptAnswer(attempt=attempt, question=q, selected_option=sel, is_correct=ok)
            for q, sel, ok in answers
        )
        Attempt.objects.filter(pk=attempt.pk).update(completed=True)
    except DatabaseError:
        logger.exception("Saving quiz attempt failed (quiz %s)", quiz.pk)
        if attempt is not None:
            try:
                attempt.delete()
            except DatabaseError:
                logger.exception("Could not remove incomplete attempt %s", attempt.pk)
        return render(
            request, "quizzes/take.html",
            {"quiz": quiz, "questions": questions,
             "error_message": "Your answers could not be saved. Please try again."},
            status=503,
        )
    # Always redirect after a successful POST (see polls.views.vote).
    return HttpResponseRedirect(reverse("quizzes:attempt", args=(attempt.pk,)))


class AttemptDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = "quizzes/attempt_detail.html"
    context_object_name = "attempt"

    def get_queryset(self):
        """Only the logged-in user's own attempts (others get 404)."""
        return Attempt.objects.completed().filter(user=self.request.user).select_related("quiz", "quiz__topic")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["answers"] = self.object.answers.select_related(
            "question", "selected_option"
        ).prefetch_related("question__options")
        return context


class AttemptListView(LoginRequiredMixin, generic.ListView):
    template_name = "quizzes/attempt_list.html"
    context_object_name = "attempts"

    def get_queryset(self):
        return Attempt.objects.completed().filter(user=self.request.user).select_related("quiz", "quiz__topic")
