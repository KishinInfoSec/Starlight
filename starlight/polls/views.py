from django.contrib.auth.decorators import login_required
import logging

from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import F
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Choice, Question, Vote
from django.views import generic
from django.utils import timezone

logger = logging.getLogger(__name__)


class IndexView(generic.ListView):
    template_name = "polls/index.html"
    context_object_name = "latest_question_list"

    def get_queryset(self):
        return Question.objects.filter(pub_date__lte=timezone.now()).order_by("-pub_date")[:5]

class DetailView(generic.DetailView):
    model = Question
    template_name = "polls/detail.html"

    def get_queryset(self):
        """
        Excludes any questions that aren't published yet.
        """
        return Question.objects.filter(pub_date__lte=timezone.now())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_voted"] = (
            self.request.user.is_authenticated
            and Vote.objects.filter(
                user=self.request.user, question=self.object
            ).exists()
        )
        return context

class ResultsView(generic.DetailView):
    model = Question
    template_name = "polls/results.html"

    def get_queryset(self):
        """
        Excludes any questions that aren't published yet.
        """
        return Question.objects.filter(pub_date__lte=timezone.now())

@login_required
def vote(request, question_id):
    question = get_object_or_404(
        Question, pk=question_id, pub_date__lte=timezone.now()
    )
    try:
        selected_choice = question.choice_set.get(pk=request.POST["choice"])
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(
            request,
            "polls/detail.html",
            {
                "question": question,
                "error_message": "You didn't select a choice.",
            },
        )
    # No transaction: the Vote row (unique per user+question) is the guard and
    # the source of truth. The conter is a cache that `recount_votes` can
    # rebuild, so a failure between the two writes is survivable.
    try:
        # Savepoint only so an IntegrityError doesn't poison an enclosing
        # transaction (tests, ATOMIC_REQUESTS); the guard is the constraint.
        with transaction.atomic():
            Vote.objects.create(
                user=request.user, question=question, choice=selected_choice
            )
    except IntegrityError:
        # The unique (user, question) constraint rejected a repeat vote.
        return render(
            request,
            "polls/detail.html",
            {
                "question": question,
                "has_voted": True,
                "error_message": "You have already voted on this question.",
            },
        )
    try:
        Choice.objects.filter(pk=selected_choice.pk).update(votes=F("votes") + 1)
    except DatabaseError:
        logger.exception(
            "Vote counter increment failed for choice %s; run recount_votes",
            selected_choice.pk,
        )
    # Always return an HttpResponseRedirect after successfully dealing
    # with POST data. This prevents data from being posted twice if a
    # user hits the Back button.
    return HttpResponseRedirect(reverse("polls:results", args=(question.id,)))
