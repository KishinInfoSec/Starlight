import datetime
from contextlib import nullcontext
from io import StringIO
from unittest import mock
from pathlib import Path

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, transaction
from django.templatetags.static import static
from django.template.loader import get_template, render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Question, Vote

# Create your tests here.

class QuestionModelTests(TestCase):
    def test_was_published_recently_with_future_question(self):
        """
        was_published_recently() returns False for questions whose pub_date
        is in the future.
        """
        time = timezone.now() + datetime.timedelta(days=30)
        future_question = Question(pub_date=time)
        self.assertIs(future_question.was_published_recently(), False)

    def test_was_published_recently_with_old_question(self):
        time = timezone.now() - datetime.timedelta(days=1, seconds=1)
        old_question = Question(pub_date=time)
        self.assertIs(old_question.was_published_recently(), False)


    def test_was_published_recently_with_recent_question(self):
        time = timezone.now() - datetime.timedelta(hours=23, minutes=59, seconds=59)
        recent_question = Question(pub_date=time)
        self.assertIs(recent_question.was_published_recently(), True)

def create_question(question_text, days):
    """
    Create a question with the given `question_text` and published the
    given number of `days` offset to now (negative for questions published
    in the past, positive for questions that have yet to be published).
    """
    time = timezone.now() + datetime.timedelta(days=days)
    return Question.objects.create(question_text=question_text, pub_date=time)


class QuestionIndexViewTests(TestCase):
    def test_no_questions(self):
        """
        If no questions exist, an appropriate message is displayed.
        """
        response = self.client.get(reverse("polls:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No polls are available.")
        self.assertQuerySetEqual(response.context["latest_question_list"], [])

    def test_past_question(self):
        """
        Questions with a pub_date in the past are displayed on the
        index page.
        """
        question = create_question(question_text="Past question.", days=-30)
        response = self.client.get(reverse("polls:index"))
        self.assertQuerySetEqual(
            response.context["latest_question_list"],
            [question],
        )

    def test_future_question(self):
        """
        Questions with a pub_date in the future aren't displayed on
        the index page.
        """
        create_question(question_text="Future question.", days=30)
        response = self.client.get(reverse("polls:index"))
        self.assertContains(response, "No polls are available.")
        self.assertQuerySetEqual(response.context["latest_question_list"], [])

    def test_future_question_and_past_question(self):
        """
        Even if both past and future questions exist, only past questions
        are displayed.
        """
        question = create_question(question_text="Past question.", days=-30)
        create_question(question_text="Future question.", days=30)
        response = self.client.get(reverse("polls:index"))
        self.assertQuerySetEqual(
            response.context["latest_question_list"],
            [question],
        )

    def test_two_past_questions(self):
        """
        The questions index page may display multiple questions.
        """
        question1 = create_question(question_text="Past question 1.", days=-30)
        question2 = create_question(question_text="Past question 2.", days=-5)
        response = self.client.get(reverse("polls:index"))
        self.assertQuerySetEqual(
            response.context["latest_question_list"],
            [question2, question1],
        )
class QuestionDetailViewTests(TestCase):
    def test_future_question(self):
        """
        The detail view of a question with a pub_date in the future
        returns a 404 not found.
        """
        future_question = create_question(question_text="Future question.", days=5)
        url = reverse("polls:detail", args=(future_question.id,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_past_question(self):
        """
        The detail view of a question with a pub_date in the past
        displays the question's text.
        """
        past_question = create_question(question_text="Past Question.", days=-5)
        url = reverse("polls:detail", args=(past_question.id,))
        response = self.client.get(url)
        self.assertContains(response, past_question.question_text)

    def test_anonymous_sees_login_link_not_vote_button(self):
        """
        Anonymous visitors see a login link (with next) and no vote button.
        """
        question = create_question(question_text="Past Question.", days=-5)
        url = reverse("polls:detail", args=(question.id,))
        response = self.client.get(url)
        self.assertContains(response, f"{reverse('accounts:login')}?next={url}")
        self.assertNotContains(response, 'id="vote-button"')

    def test_logged_in_sees_vote_button(self):
        """
        Logged-in users who haven't voted see the vote button.
        """
        user = get_user_model().objects.create_user(
            "voter", "voter@example.com", "S3cure-pass-phrase"
        )
        self.client.force_login(user)
        question = create_question(question_text="Past Question.", days=-5)
        response = self.client.get(reverse("polls:detail", args=(question.id,)))
        self.assertContains(response, 'id="vote-button"')
        self.assertIs(response.context["has_voted"], False)

    def test_voted_user_sees_already_voted_note(self):
        """
        Users who already voted see a note instead of the vote button.
        """
        user = get_user_model().objects.create_user(
            "voter", "voter@example.com", "S3cure-pass-phrase"
        )
        self.client.force_login(user)
        question = create_question(question_text="Past Question.", days=-5)
        choice = question.choice_set.create(choice_text="A")
        Vote.objects.create(user=user, question=question, choice=choice)
        response = self.client.get(reverse("polls:detail", args=(question.id,)))
        self.assertIs(response.context["has_voted"], True)
        self.assertContains(response, "You have already voted on this question.")
        self.assertNotContains(response, 'id="vote-button"')

class QuestionResultsViewTests(TestCase):
    def test_future_question(self):
        """
        The results view of a question with a pub_date in the future
        returns a 404 not found.
        """
        future_question = create_question(question_text="Future question.", days=5)
        url = reverse("polls:results", args=(future_question.id,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_past_question(self):
        """
        The results view of a question with a pub_date in the past
        displays the question's text.
        """
        past_question = create_question(question_text="Past Question.", days=-5)
        url = reverse("polls:results", args=(past_question.id,))
        response = self.client.get(url)
        self.assertContains(response, past_question.question_text)


class VoteModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("voter", "voter@example.com", "S3cure-pass-phrase")
        self.other = User.objects.create_user("other", "other@example.com", "S3cure-pass-phrase")
        self.question = create_question("Q1", -1)
        self.choice1 = self.question.choice_set.create(choice_text="A")
        self.choice2 = self.question.choice_set.create(choice_text="B")

    def test_one_vote_per_user_per_question(self):
        """
        A user cannot have two votes on the same question, even for
        different choices.
        """
        Vote.objects.create(user=self.user, question=self.question, choice=self.choice1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(user=self.user, question=self.question, choice=self.choice2)

    def test_same_user_can_vote_on_different_questions(self):
        """
        One user may vote once on each of several questions.
        """
        question2 = create_question("Q2", -1)
        choice = question2.choice_set.create(choice_text="C")
        Vote.objects.create(user=self.user, question=self.question, choice=self.choice1)
        Vote.objects.create(user=self.user, question=question2, choice=choice)
        self.assertEqual(Vote.objects.filter(user=self.user).count(), 2)

    def test_different_users_can_vote_on_same_question(self):
        """
        Different users may each vote on the same question.
        """
        Vote.objects.create(user=self.user, question=self.question, choice=self.choice1)
        Vote.objects.create(user=self.other, question=self.question, choice=self.choice1)
        self.assertEqual(Vote.objects.filter(question=self.question).count(), 2)


class VoteViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "voter", "voter@example.com", "S3cure-pass-phrase"
        )
        self.client.force_login(self.user)

    def test_future_question(self):
        """
        Voting on a question with a pub_date in the future returns a 404
        and records no vote.
        """
        future_question = create_question(question_text="Future question.", days=5)
        choice = future_question.choice_set.create(choice_text="A", votes=0)
        url = reverse("polls:vote", args=(future_question.id,))
        response = self.client.post(url, {"choice": choice.id})
        self.assertEqual(response.status_code, 404)
        choice.refresh_from_db()
        self.assertEqual(choice.votes, 0)

    def test_no_choice_selected(self):
        """
        Posting without a choice redisplays the form with an error message.
        """
        question = create_question(question_text="Past question.", days=-5)
        url = reverse("polls:vote", args=(question.id,))
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You didn&#x27;t select a choice.")

    def test_valid_choice(self):
        """
        Posting a valid choice increments its vote count and redirects to
        the results page.
        """
        question = create_question(question_text="Past question.", days=-5)
        choice = question.choice_set.create(choice_text="A", votes=0)
        url = reverse("polls:vote", args=(question.id,))
        response = self.client.post(url, {"choice": choice.id})
        self.assertRedirects(response, reverse("polls:results", args=(question.id,)))
        choice.refresh_from_db()
        self.assertEqual(choice.votes, 1)

    def test_anonymous_redirected_to_login(self):
        """
        An anonymous POST is redirected to login with `next` and records
        nothing.
        """
        question = create_question(question_text="Past question.", days=-5)
        choice = question.choice_set.create(choice_text="A", votes=0)
        url = reverse("polls:vote", args=(question.id,))
        self.client.logout()
        response = self.client.post(url, {"choice": choice.id})
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
            fetch_redirect_response=False,
        )
        choice.refresh_from_db()
        self.assertEqual(choice.votes, 0)
        self.assertEqual(Vote.objects.count(), 0)

    def test_valid_choice_records_vote_row(self):
        """
        A valid vote creates a Vote row for the user, question and choice.
        """
        question = create_question(question_text="Past question.", days=-5)
        choice = question.choice_set.create(choice_text="A", votes=0)
        url = reverse("polls:vote", args=(question.id,))
        self.client.post(url, {"choice": choice.id})
        self.assertEqual(
            Vote.objects.get(user=self.user, question=question).choice, choice
        )

    def test_second_vote_rejected(self):
        """
        A second vote by the same user is rejected and changes no counts.
        """
        question = create_question(question_text="Past question.", days=-5)
        choice_a = question.choice_set.create(choice_text="A", votes=0)
        choice_b = question.choice_set.create(choice_text="B", votes=0)
        url = reverse("polls:vote", args=(question.id,))
        first = self.client.post(url, {"choice": choice_a.id})
        self.assertEqual(first.status_code, 302)
        response = self.client.post(url, {"choice": choice_b.id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You have already voted on this question.")
        choice_a.refresh_from_db()
        choice_b.refresh_from_db()
        self.assertEqual(choice_a.votes, 1)
        self.assertEqual(choice_b.votes, 0)
        self.assertEqual(Vote.objects.count(), 1)

    def test_other_user_can_still_vote(self):
        """
        Another user can vote on a question the first user already voted on.
        """
        question = create_question(question_text="Past question.", days=-5)
        choice = question.choice_set.create(choice_text="A", votes=0)
        url = reverse("polls:vote", args=(question.id,))
        self.client.post(url, {"choice": choice.id})
        user2 = get_user_model().objects.create_user(
            "voter2", "voter2@example.com", "S3cure-pass-phrase"
        )
        self.client.force_login(user2)
        response = self.client.post(url, {"choice": choice.id})
        self.assertEqual(response.status_code, 302)
        choice.refresh_from_db()
        self.assertEqual(choice.votes, 2)


class AdminTemplateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin", "admin@example.com", "pw")
        self.client.force_login(self.user)

    def test_admin_index_uses_stock_admin_layout(self):
        """
        Admin pages render Django's admin/base.html (stylesheet, header,
        user tools) rather than the public site base.html.
        """
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, static("admin/css/base.css"))
        self.assertContains(response, 'id="site-name"')
        self.assertContains(response, 'id="user-tools"')
        self.assertContains(response, 'id="recent-actions-module"')

    def test_admin_header_uses_site_header(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, admin.site.site_header)
        self.assertEqual(admin.site.site_header, "Kishinlabs Administration")

    def test_admin_loads_theme_stylesheet(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, static("starlight/admin-theme.css"))

    def test_no_project_overrides_of_stock_admin_templates(self):
        """
        Only admin/base_site.html is overridden; base.html, index.html,
        app_index.html and app_list.html come from django.contrib.admin.
        """
        for name in ("base", "index", "app_index", "app_list"):
            path = Path(get_template(f"admin/{name}.html").origin.name)
            self.assertIn("django/contrib/admin", path.as_posix(), name)


class StaticFilesTests(SimpleTestCase):
    def test_admin_theme_is_findable(self):
        self.assertIsNotNone(finders.find("starlight/admin-theme.css"))

    def test_project_does_not_shadow_admin_static_namespace(self):
        """
        No project file overrides a django.contrib.admin static file.
        """
        for path in ("admin/css/dashboard.css", "admin/css/base.css"):
            self.assertIn("django/contrib/admin", Path(finders.find(path)).as_posix())
        self.assertIsNone(finders.find("admin/css/style.css"))

    def test_polls_page_does_not_link_admin_stylesheet(self):
        html = render_to_string("polls/index.html", {"latest_question_list": []})
        self.assertNotIn("admin/css/", html)
        self.assertIn(static("starlight/site.css"), html)

    def test_site_stylesheet_linked_once(self):
        html = render_to_string("polls/index.html", {"latest_question_list": []})
        self.assertEqual(html.count(static("starlight/site.css")), 1)

    def test_site_stylesheet_has_no_admin_dashboard_rules(self):
        css = Path(finders.find("starlight/site.css")).read_text()
        self.assertNotIn(".dashboard", css)
        self.assertNotIn("actionlist", css)


class VoteWithoutTransactionTests(TestCase):
    """Correctness must not rely on transaction.atomic() (some database backends have no transactions)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "voter", "voter@example.com", "S3cure-pass-phrase"
        )
        self.client.force_login(self.user)
        self.question = create_question(question_text="Past question.", days=-5)
        self.choice = self.question.choice_set.create(choice_text="A", votes=0)
        self.url = reverse("polls:vote", args=(self.question.id,))

    def fail_increment(self):
        return mock.patch("polls.views.Choice.objects.filter", side_effect=DatabaseError("boom"))

    def test_failed_increment_keeps_vote_and_no_500(self):
        with self.fail_increment():
            response = self.client.post(self.url, {"choice": self.choice.id})
        self.assertRedirects(response, reverse("polls:results", args=(self.question.id,)))
        self.assertEqual(Vote.objects.filter(user=self.user, question=self.question).count(), 1)

    def test_no_double_vote_after_failed_increment(self):
        with self.fail_increment():
            self.client.post(self.url, {"choice": self.choice.id})
        response = self.client.post(self.url, {"choice": self.choice.id})
        self.assertContains(response, "You have already voted on this question.")
        self.assertEqual(Vote.objects.count(), 1)
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 0)  # lost increment, repairable

    def test_recount_repairs_lost_increment(self):
        with self.fail_increment():
            self.client.post(self.url, {"choice": self.choice.id})
        call_command("recount_votes", stdout=StringIO())
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 1)

    def test_works_with_atomic_as_noop(self):
        with mock.patch("django.db.transaction.atomic", lambda *a, **k: nullcontext()):
            response = self.client.post(self.url, {"choice": self.choice.id})
        self.assertEqual(response.status_code, 302)
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.votes, 1)


class RecountVotesCommandTests(TestCase):
    def test_recomputes_votes_from_vote_rows(self):
        User = get_user_model()
        question = create_question(question_text="Q.", days=-1)
        a = question.choice_set.create(choice_text="A", votes=7)
        b = question.choice_set.create(choice_text="B", votes=0)
        c = question.choice_set.create(choice_text="C", votes=3)  # no vote rows
        for i, choice in enumerate([a, a, b]):
            user = User.objects.create_user(f"u{i}", f"u{i}@example.com", "S3cure-pass-phrase")
            Vote.objects.create(user=user, question=question, choice=choice)
        out = StringIO()
        call_command("recount_votes", stdout=out)
        for choice, expected in ((a, 2), (b, 1), (c, 0)):
            choice.refresh_from_db()
            self.assertEqual(choice.votes, expected)
        self.assertIn("Updated 3", out.getvalue())

    def test_dry_run_changes_nothing(self):
        question = create_question(question_text="Q.", days=-1)
        a = question.choice_set.create(choice_text="A", votes=7)
        out = StringIO()
        call_command("recount_votes", "--dry-run", stdout=out)
        a.refresh_from_db()
        self.assertEqual(a.votes, 7)
        self.assertIn("1 would change", out.getvalue())
