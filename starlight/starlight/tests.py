from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(response, reverse("polls:index"))

    def test_brand_links_home(self):
        response = self.client.get("/")
        self.assertContains(response, f'<a class="brand" href="{reverse("home")}">')

    def test_home_lists_quizzes(self):
        response = self.client.get("/")
        cards = response.content.decode().partition('<ul class="poll-list">')[2].partition("</ul>")[0]
        self.assertIn(f'href="{reverse("quizzes:index")}"', cards)


class SiteShellTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "alice", "alice@example.com", "S3cure-pass-phrase"
        )

    def split_header_footer(self, html):
        before, sep, after = html.partition("<footer")
        self.assertTrue(sep, "page has no <footer")
        return before, after

    def test_admin_link_in_footer_not_header(self):
        response = self.client.get("/")
        before, after = self.split_header_footer(response.content.decode())
        self.assertNotIn(reverse("admin:index"), before)
        self.assertIn(reverse("admin:index"), after)

    def test_anonymous_header_shows_login_and_signup(self):
        response = self.client.get("/")
        self.assertContains(response, reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:signup"))
        self.assertNotContains(response, reverse("accounts:logout"))

    def test_authenticated_header_shows_username_and_logout_form(self):
        self.client.force_login(self.user)
        response = self.client.get("/")
        self.assertContains(response, "alice")
        self.assertContains(response, f'action="{reverse("accounts:logout")}"')
        self.assertContains(response, 'method="post"')
        self.assertNotContains(response, reverse("accounts:signup"))

    def test_polls_pages_share_shell(self):
        response = self.client.get(reverse("polls:index"))
        self.assertEqual(response.status_code, 200)
        before, after = self.split_header_footer(response.content.decode())
        self.assertNotIn(reverse("admin:index"), before)
        self.assertIn(reverse("admin:index"), after)

    def test_nav_has_quizzes_link(self):
        response = self.client.get("/")
        before, _ = self.split_header_footer(response.content.decode())
        self.assertIn(f'href="{reverse("quizzes:index")}"', before)
