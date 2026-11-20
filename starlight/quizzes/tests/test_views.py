import datetime
from contextlib import nullcontext
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from quizzes.models import Attempt, AttemptAnswer, Option, Quiz
from quizzes.tests.helpers import add_question, create_quiz, create_topic, create_user


class TopicListViewTests(TestCase):
    def test_lists_topics_with_published_quizzes(self):
        """Topics with a published quiz are listed with a count; others are hidden."""
        a = create_topic("Networking")
        create_quiz(a, "Ports 101", days=-1)
        b = create_topic("Cryptography")
        create_quiz(b, "Future Crypto", days=5)
        resp = self.client.get(reverse("quizzes:index"))
        self.assertContains(resp, "Networking")
        self.assertContains(resp, "1 quiz")
        self.assertNotContains(resp, "Cryptography")

    def test_empty_state(self):
        """With no content the empty message is shown."""
        resp = self.client.get(reverse("quizzes:index"))
        self.assertContains(resp, "No quizzes are available yet.")


class TopicDetailViewTests(TestCase):
    def test_lists_only_published_quizzes(self):
        """Past quizzes are shown, future ones hidden."""
        t = create_topic()
        create_quiz(t, "Ports 101", days=-1)
        create_quiz(t, "Secret Future", days=3)
        resp = self.client.get(reverse("quizzes:topic", args=(t.slug,)))
        self.assertContains(resp, "Ports 101")
        self.assertNotContains(resp, "Secret Future")

    def test_unknown_topic_404(self):
        """An unknown topic slug is a 404."""
        resp = self.client.get(reverse("quizzes:topic", args=("nope",)))
        self.assertEqual(resp.status_code, 404)


class QuizDetailViewTests(TestCase):
    def setUp(self):
        self.topic = create_topic()

    def test_future_quiz_404(self):
        """Unpublished quizzes are not reachable."""
        quiz = create_quiz(self.topic, days=5)
        resp = self.client.get(reverse("quizzes:detail", args=(quiz.slug,)))
        self.assertEqual(resp.status_code, 404)

    def test_past_quiz_shows_title_and_question_count(self):
        """The page shows the title and the number of questions."""
        quiz = create_quiz(self.topic)
        add_question(quiz)
        add_question(quiz, text="Second?")
        resp = self.client.get(reverse("quizzes:detail", args=(quiz.slug,)))
        self.assertContains(resp, "Ports 101")
        self.assertContains(resp, "2 questions")

    def test_anonymous_sees_login_link(self):
        """Anonymous visitors get a login link and no start button."""
        quiz = create_quiz(self.topic)
        add_question(quiz)
        url = reverse("quizzes:detail", args=(quiz.slug,))
        resp = self.client.get(url)
        self.assertContains(resp, f"{reverse('accounts:login')}?next={url}")
        self.assertNotContains(resp, 'id="start-quiz"')

    def test_logged_in_sees_start_button(self):
        """Logged-in users see the start button and 'No attempts yet'."""
        quiz = create_quiz(self.topic)
        add_question(quiz)
        self.client.force_login(create_user("alice"))
        resp = self.client.get(reverse("quizzes:detail", args=(quiz.slug,)))
        self.assertContains(resp, 'id="start-quiz"')
        self.assertContains(resp, "No attempts yet")

    def test_logged_in_sees_best_score_and_attempt_count(self):
        """Best score and attempt count come from the user's attempts."""
        quiz = create_quiz(self.topic)
        add_question(quiz)
        user = create_user("alice")
        Attempt.objects.create(user=user, quiz=quiz, score=1, total=2, completed=True)
        Attempt.objects.create(user=user, quiz=quiz, score=2, total=2, completed=True)
        self.client.force_login(user)
        resp = self.client.get(reverse("quizzes:detail", args=(quiz.slug,)))
        self.assertContains(resp, "Best: 2/2 (100%)")
        self.assertContains(resp, "2 attempts")

    def test_no_questions_hides_start(self):
        """A quiz without questions cannot be started."""
        quiz = create_quiz(self.topic)
        self.client.force_login(create_user("alice"))
        resp = self.client.get(reverse("quizzes:detail", args=(quiz.slug,)))
        self.assertContains(resp, "This quiz has no questions yet.")
        self.assertNotContains(resp, 'id="start-quiz"')


class TakeQuizViewTests(TestCase):
    def setUp(self):
        self.user = create_user("alice")
        self.client.force_login(self.user)
        self.topic = create_topic()
        self.quiz = create_quiz(self.topic)
        self.questions = [
            add_question(self.quiz, text=f"Question number {i}?", order=i,
                         options=((f"right {i}", True), (f"wrong {i}", False)))
            for i in range(3)
        ]
        self.url = reverse("quizzes:take", args=(self.quiz.slug,))

    def correct(self, q):
        return q.options.get(is_correct=True)

    def wrong(self, q):
        return q.options.get(is_correct=False)

    def test_anonymous_redirected_to_login(self):
        """Anonymous users are sent to login."""
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={self.url}",
                             fetch_redirect_response=False)

    def test_future_quiz_404(self):
        """Unpublished quizzes can't be taken (GET or POST)."""
        future = create_quiz(self.topic, "Future", days=3)
        add_question(future)
        url = reverse("quizzes:take", args=(future.slug,))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.assertEqual(Attempt.objects.count(), 0)

    def test_get_renders_every_question_and_option(self):
        """The form shows all questions and options, and leaks no answer key."""
        resp = self.client.get(self.url)
        for q in self.questions:
            self.assertContains(resp, q.text)
            for o in q.options.all():
                self.assertContains(resp, f'name="question-{q.pk}"')
                self.assertContains(resp, f'value="{o.pk}"')
        self.assertContains(resp, 'id="submit-quiz"')
        self.assertNotContains(resp, "is_correct")

    def test_all_correct(self):
        """All correct answers score 3/3 and redirect to the attempt."""
        data = {f"question-{q.pk}": self.correct(q).pk for q in self.questions}
        resp = self.client.post(self.url, data)
        attempt = Attempt.objects.get()
        self.assertEqual((attempt.score, attempt.total), (3, 3))
        self.assertEqual(attempt.user, self.user)
        self.assertEqual(attempt.answers.count(), 3)
        self.assertTrue(all(a.is_correct for a in attempt.answers.all()))
        self.assertRedirects(resp, reverse("quizzes:attempt", args=(attempt.pk,)))

    def test_partial_and_skipped(self):
        """One right, one wrong, one skipped is 1/3."""
        q0, q1, q2 = self.questions
        self.client.post(self.url, {
            f"question-{q0.pk}": self.correct(q0).pk,
            f"question-{q1.pk}": self.wrong(q1).pk,
        })
        attempt = Attempt.objects.get()
        self.assertEqual((attempt.score, attempt.total), (1, 3))
        skipped = attempt.answers.get(question=q2)
        self.assertIsNone(skipped.selected_option)
        self.assertFalse(skipped.is_correct)
        self.assertEqual(attempt.answers.get(question=q1).selected_option, self.wrong(q1))

    def test_option_from_other_question_counts_as_wrong(self):
        """An option belonging to another question is ignored."""
        q0, q1, _ = self.questions
        self.client.post(self.url, {f"question-{q0.pk}": self.correct(q1).pk})
        attempt = Attempt.objects.get()
        ans = attempt.answers.get(question=q0)
        self.assertFalse(ans.is_correct)
        self.assertIsNone(ans.selected_option)
        self.assertEqual(attempt.score, 0)

    def test_garbage_values_dont_crash(self):
        """Non-numeric or empty values are skipped, not a 500."""
        q0, q1, _ = self.questions
        resp = self.client.post(self.url, {
            f"question-{q0.pk}": "abc",
            f"question-{q1.pk}": "",
        })
        self.assertEqual(resp.status_code, 302)
        attempt = Attempt.objects.get()
        self.assertEqual(attempt.score, 0)
        self.assertEqual(attempt.answers.filter(selected_option__isnull=True).count(), 3)

    def test_retake_creates_new_attempt(self):
        """Each submission creates a new attempt."""
        self.client.post(self.url, {})
        self.client.post(self.url, {})
        self.assertEqual(Attempt.objects.count(), 2)

    def test_quiz_without_questions(self):
        """An empty quiz shows a message on GET and creates nothing on POST."""
        empty = create_quiz(self.topic, "Empty One")
        url = reverse("quizzes:take", args=(empty.slug,))
        resp = self.client.get(url)
        self.assertContains(resp, "This quiz has no questions yet.")
        self.assertNotContains(resp, 'id="submit-quiz"')
        resp = self.client.post(url, {})
        self.assertRedirects(resp, reverse("quizzes:detail", args=(empty.slug,)))
        self.assertEqual(Attempt.objects.count(), 0)

    def test_score_snapshot_survives_quiz_edit(self):
        """Editing the answer key later doesn't change stored results."""
        data = {f"question-{q.pk}": self.correct(q).pk for q in self.questions}
        self.client.post(self.url, data)
        for q in self.questions:
            right, wrong = self.correct(q), self.wrong(q)
            Option.objects.filter(pk=right.pk).update(is_correct=False)
            Option.objects.filter(pk=wrong.pk).update(is_correct=True)
        attempt = Attempt.objects.get()
        self.assertEqual(attempt.score, 3)
        self.assertTrue(all(a.is_correct for a in AttemptAnswer.objects.filter(attempt=attempt)))


class AttemptDetailViewTests(TestCase):
    def setUp(self):
        self.user = create_user("alice")
        self.quiz = create_quiz(create_topic())
        self.qs = [
            add_question(self.quiz, text=f"Review question {i}?", order=i,
                         options=((f"right {i}", True), (f"wrong {i}", False)),
                         explanation=f"Because reason {i}.")
            for i in range(3)
        ]
        self.attempt = Attempt.objects.create(user=self.user, quiz=self.quiz, score=2, total=3, completed=True)
        for i, q in enumerate(self.qs):
            ok = i < 2
            AttemptAnswer.objects.create(
                attempt=self.attempt, question=q, is_correct=ok,
                selected_option=q.options.get(is_correct=ok),
            )
        self.url = reverse("quizzes:attempt", args=(self.attempt.pk,))

    def test_owner_sees_review(self):
        """The owner sees score, picks, correct answers and explanations."""
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertContains(resp, "2/3")
        self.assertContains(resp, "67%")
        for i, q in enumerate(self.qs):
            self.assertContains(resp, q.text)
            self.assertContains(resp, f"right {i}")
            self.assertContains(resp, f"Because reason {i}.")
        self.assertContains(resp, "wrong 2")

    def test_other_user_gets_404(self):
        """Someone else's attempt is a 404."""
        self.client.force_login(create_user("bob"))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_anonymous_redirected_to_login(self):
        """Anonymous users are sent to login."""
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={self.url}",
                             fetch_redirect_response=False)


class AttemptListViewTests(TestCase):
    def test_lists_only_own_attempts_newest_first(self):
        """Own attempts only, newest first."""
        alice, bob = create_user("alice"), create_user("bob")
        topic = create_topic()
        old = create_quiz(topic, "Older Quiz")
        new = create_quiz(topic, "Newer Quiz")
        other = create_quiz(topic, "Bobs Quiz")
        a1 = Attempt.objects.create(user=alice, quiz=old, score=1, total=2, completed=True)
        a2 = Attempt.objects.create(user=alice, quiz=new, score=2, total=2, completed=True)
        Attempt.objects.create(user=bob, quiz=other, score=0, total=2, completed=True)
        now = timezone.now()
        Attempt.objects.filter(pk=a1.pk).update(created=now - datetime.timedelta(days=2))
        Attempt.objects.filter(pk=a2.pk).update(created=now - datetime.timedelta(days=1))
        self.client.force_login(alice)
        resp = self.client.get(reverse("quizzes:attempts"))
        self.assertNotContains(resp, "Bobs Quiz")
        self.assertEqual(list(resp.context["attempts"]), [a2, a1])
        self.assertContains(resp, "Newer Quiz")

    def test_empty_state(self):
        """No attempts shows the empty message."""
        self.client.force_login(create_user("alice"))
        resp = self.client.get(reverse("quizzes:attempts"))
        self.assertContains(resp, "You haven't taken any quizzes yet.")

    def test_anonymous_redirected_to_login(self):
        """Anonymous users are sent to login."""
        url = reverse("quizzes:attempts")
        resp = self.client.get(url)
        self.assertRedirects(resp, f"{reverse('accounts:login')}?next={url}",
                             fetch_redirect_response=False)


class TakeWithoutTransactionTests(TestCase):
    """A failure between writes must leave no counted attempt (atomic() may be a no-op on some backends)."""

    def setUp(self):
        self.user = create_user("alice")
        self.client.force_login(self.user)
        self.quiz = create_quiz(create_topic())
        self.qs = [add_question(self.quiz, text=f"Q{i}?", order=i) for i in range(2)]
        self.url = reverse("quizzes:take", args=(self.quiz.slug,))
        self.data = {f"question-{q.pk}": q.options.get(is_correct=True).pk for q in self.qs}

    def assert_nothing_counted(self):
        self.assertFalse(Attempt.objects.filter(completed=True).exists())
        resp = self.client.get(reverse("quizzes:attempts"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context["attempts"]), [])
        resp = self.client.get(reverse("quizzes:detail", args=(self.quiz.slug,)))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["best_attempt"])
        self.assertEqual(resp.context["attempt_count"], 0)
        for attempt in Attempt.objects.all():
            r = self.client.get(reverse("quizzes:attempt", args=(attempt.pk,)))
            self.assertEqual(r.status_code, 404)

    def noop_atomic(self):
        return mock.patch("django.db.transaction.atomic", lambda *a, **k: nullcontext())

    def test_failed_answer_write_counts_nothing(self):
        with self.noop_atomic(), mock.patch(
            "quizzes.views.AttemptAnswer.objects.bulk_create", side_effect=DatabaseError("boom")
        ):
            resp = self.client.post(self.url, self.data)
        self.assertEqual(resp.status_code, 503)
        self.assertContains(resp, "could not be saved", status_code=503)
        self.assert_nothing_counted()

    def test_failed_final_write_counts_nothing(self):
        with self.noop_atomic(), mock.patch(
            "quizzes.views.Attempt.objects.filter", side_effect=DatabaseError("boom")
        ):
            resp = self.client.post(self.url, self.data)
        self.assertEqual(resp.status_code, 503)
        self.assert_nothing_counted()

    def test_retry_after_failure_succeeds(self):
        with mock.patch(
            "quizzes.views.AttemptAnswer.objects.bulk_create", side_effect=DatabaseError("boom")
        ):
            self.client.post(self.url, self.data)
        resp = self.client.post(self.url, self.data)
        self.assertEqual(resp.status_code, 302)
        attempt = Attempt.objects.get(completed=True)
        self.assertEqual(attempt.answers.count(), 2)
        self.assertEqual(attempt.score, 2)

    def test_incomplete_attempt_hidden_even_if_cleanup_fails(self):
        with mock.patch(
            "quizzes.views.AttemptAnswer.objects.bulk_create", side_effect=DatabaseError("boom")
        ), mock.patch("quizzes.views.Attempt.delete", side_effect=DatabaseError("boom")):
            resp = self.client.post(self.url, self.data)
        self.assertEqual(resp.status_code, 503)
        self.assertTrue(Attempt.objects.filter(completed=False).exists())
        self.assert_nothing_counted()

    def test_successful_take_is_completed(self):
        with self.noop_atomic():
            resp = self.client.post(self.url, self.data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Attempt.objects.get().completed)
