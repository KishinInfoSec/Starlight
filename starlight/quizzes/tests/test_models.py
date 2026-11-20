from django.db import IntegrityError, transaction
from django.test import TestCase

from quizzes.models import Attempt, AttemptAnswer, Option

from .helpers import add_question, create_quiz, create_topic, create_user


class QuizModelTests(TestCase):
    def test_str_methods(self):
        """__str__ of each model is its human-readable text."""
        topic = create_topic("Networking")
        quiz = create_quiz(topic, "Ports 101")
        question = add_question(quiz, text="x" * 80)
        option = question.options.get(is_correct=True)
        self.assertEqual(str(topic), "Networking")
        self.assertEqual(str(quiz), "Ports 101")
        self.assertEqual(str(question), "x" * 50)
        self.assertEqual(str(option), "443")

    def test_questions_ordered_by_order_then_id(self):
        """Questions come back sorted by order, then id."""
        quiz = create_quiz(create_topic())
        second = add_question(quiz, text="second", order=2)
        first = add_question(quiz, text="first", order=1)
        self.assertEqual(list(quiz.questions.all()), [first, second])


class OptionConstraintTests(TestCase):
    def setUp(self):
        self.question = add_question(create_quiz(create_topic()))

    def test_only_one_correct_option_per_question(self):
        """A second correct option for the same question is rejected."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            Option.objects.create(question=self.question, text="x", is_correct=True)

    def test_many_incorrect_options_allowed(self):
        """Any number of incorrect options is fine."""
        for text in ("a", "b", "c"):
            Option.objects.create(question=self.question, text=text, is_correct=False)
        self.assertEqual(self.question.options.filter(is_correct=False).count(), 4)


class AttemptModelTests(TestCase):
    def test_attempt_percent(self):
        """percent rounds to a whole number and is 0 when total is 0."""
        self.assertEqual(Attempt(score=2, total=3).percent, 67)
        self.assertEqual(Attempt(score=0, total=0).percent, 0)

    def test_one_answer_per_question_per_attempt(self):
        """A second answer for the same (attempt, question) is rejected."""
        quiz = create_quiz(create_topic())
        question = add_question(quiz)
        attempt = Attempt.objects.create(user=create_user("alice"), quiz=quiz, score=1, total=1)
        AttemptAnswer.objects.create(attempt=attempt, question=question, is_correct=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttemptAnswer.objects.create(attempt=attempt, question=question, is_correct=False)


class AttemptCompletedTests(TestCase):
    def test_default_incomplete_and_queryset_filter(self):
        user, quiz = create_user("alice"), create_quiz(create_topic())
        pending = Attempt.objects.create(user=user, quiz=quiz, score=1, total=1)
        done = Attempt.objects.create(user=user, quiz=quiz, score=1, total=1, completed=True)
        self.assertFalse(pending.completed)
        self.assertEqual(list(Attempt.objects.completed()), [done])
