from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.forms import SignUpForm
from accounts.models import User


class UserModelTests(TestCase):
    def test_auth_user_model_is_custom(self):
        """The project uses accounts.User as its user model."""
        self.assertIs(get_user_model(), User)
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")

    def test_email_required(self):
        """A user without an email fails validation."""
        with self.assertRaises(ValidationError) as ctx:
            User(username="a", email="").full_clean()
        self.assertIn("email", ctx.exception.message_dict)

    def test_email_unique_case_insensitive_in_db(self):
        """The database rejects emails that differ only by case."""
        User.objects.create_user("a", "a@example.com", "S3cure-pass-phrase")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("b", "A@Example.com", "S3cure-pass-phrase")

    def test_create_superuser_requires_email(self):
        """create_superuser works with an email, since REQUIRED_FIELDS keeps it."""
        user = User.objects.create_superuser("root", "root@example.com", "x")
        self.assertTrue(user.is_superuser)


PASSWORD = "S3cure-pass-phrase"


def signup_data(**overrides):
    data = {
        "username": "alice",
        "email": "alice@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
    }
    data.update(overrides)
    return data


class SignUpFormTests(TestCase):
    def test_valid_data_creates_user_with_email(self):
        """Valid data saves a user with their email and a usable password."""
        form = SignUpForm(signup_data())
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        user = User.objects.get(username="alice")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.check_password(PASSWORD))

    def test_email_required(self):
        """A blank email is rejected on the email field."""
        form = SignUpForm(signup_data(email=""))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_invalid_email_rejected(self):
        """A malformed email is rejected on the email field."""
        form = SignUpForm(signup_data(email="not-an-email"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_email_rejected_case_insensitive(self):
        """An email that differs only by case from an existing one is rejected."""
        User.objects.create_user("bob", "bob@example.com", PASSWORD)
        form = SignUpForm(signup_data(username="bobby", email="BOB@Example.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_concurrent_duplicate_signup_blocked_by_db(self):
        """Two forms validated before either saves: the database blocks the second."""
        first = SignUpForm(signup_data(username="one", email="a@x.com"))
        second = SignUpForm(signup_data(username="two", email="A@X.com"))
        self.assertTrue(first.is_valid(), first.errors)
        self.assertTrue(second.is_valid(), second.errors)
        first.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.save()


class SignUpViewTests(TestCase):
    def test_get_renders_form(self):
        """The sign up page renders a form with an email field."""
        response = self.client.get(reverse("accounts:signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')

    def test_post_creates_user_logs_in_and_redirects_home(self):
        """A valid sign up creates the user, logs them in and redirects home."""
        response = self.client.post(reverse("accounts:signup"), signup_data())
        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(username="alice")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_post_invalid_rerenders_with_errors(self):
        """An invalid sign up re-renders the form and creates no user."""
        response = self.client.post(
            reverse("accounts:signup"), signup_data(email="not-an-email")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="alice").exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("carol", "carol@example.com", PASSWORD)

    def test_login_page_renders(self):
        """The login page renders with the accounts template."""
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_login_redirects_home(self):
        """A successful login redirects to the home page."""
        response = self.client.post(
            reverse("accounts:login"), {"username": "carol", "password": PASSWORD}
        )
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_login_honours_next(self):
        """A successful login redirects to a safe next URL."""
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "carol", "password": PASSWORD, "next": "/polls/"},
        )
        self.assertRedirects(response, "/polls/", fetch_redirect_response=False)

    def test_logout_requires_post_and_logs_out(self):
        """Logout is POST-only and ends the session."""
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
