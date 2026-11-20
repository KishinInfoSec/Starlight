from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from django.test import TestCase
from django.urls import reverse

from quizzes.admin import OptionInlineFormSet
from quizzes.models import Option, Question

from .helpers import PASSWORD, add_question, create_quiz, create_topic

OptionFormSet = inlineformset_factory(
    Question, Option, formset=OptionInlineFormSet, fields=["text", "is_correct"],
    extra=0, min_num=2, validate_min=True, can_delete=True,
)


def option_data(options):
    """Build POST data for the `options` formset from (text, correct, deleted) tuples."""
    data = {
        "options-TOTAL_FORMS": str(len(options)),
        "options-INITIAL_FORMS": "0",
        "options-MIN_NUM_FORMS": "0",
        "options-MAX_NUM_FORMS": "1000",
    }
    for i, (text, correct, deleted) in enumerate(options):
        data[f"options-{i}-text"] = text
        if correct:
            data[f"options-{i}-is_correct"] = "on"
        if deleted:
            data[f"options-{i}-DELETE"] = "on"
    return data


class OptionInlineFormSetTests(TestCase):
    def setUp(self):
        quiz = create_quiz(create_topic())
        self.question = add_question(quiz, options=())

    def formset(self, options):
        return OptionFormSet(option_data(options), instance=self.question, prefix="options")

    def test_exactly_one_correct_is_valid(self):
        """A question with exactly one correct option passes validation."""
        formset = self.formset([("443", True, False), ("80", False, False)])
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_no_correct_option_is_invalid(self):
        """Having no correct option is rejected with the exactly-one message."""
        formset = self.formset([("443", False, False), ("80", False, False)])
        self.assertFalse(formset.is_valid())
        self.assertIn("exactly one correct option", " ".join(formset.non_form_errors()))

    def test_two_correct_options_is_invalid(self):
        """Two correct options are rejected with the exactly-one message."""
        formset = self.formset([("443", True, False), ("80", True, False)])
        self.assertFalse(formset.is_valid())
        self.assertIn("exactly one correct option", " ".join(formset.non_form_errors()))

    def test_fewer_than_two_options_is_invalid(self):
        """Fewer than two options fails the minimum-number check."""
        formset = self.formset([("443", True, False)])
        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_deleted_correct_option_not_counted(self):
        """A correct option marked for deletion does not count toward the one-correct rule."""
        formset = self.formset([
            ("443", True, False),
            ("8443", True, True),
            ("80", False, False),
        ])
        self.assertTrue(formset.is_valid(), formset.errors)


class QuizAdminPagesTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_superuser("admin", "admin@example.com", PASSWORD)
        self.client.force_login(get_user_model().objects.get(username="admin"))

    def test_add_pages_render(self):
        """Quiz, question, topic add pages and the attempt changelist return 200."""
        for name in ["admin:quizzes_quiz_add", "admin:quizzes_question_add",
                     "admin:quizzes_topic_add", "admin:quizzes_attempt_changelist"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_question_add_page_has_option_formset(self):
        """The question add page renders the inline options formset."""
        response = self.client.get(reverse("admin:quizzes_question_add"))
        self.assertContains(response, 'name="options-TOTAL_FORMS"')
