from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from ctf.models import (Challenge, Membership, PracticeGroup, SkillObjective,
                        Solve, Submission)
from accounts.models import User
from .helpers import make_challenge


class AdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.su = User.objects.create_superuser("root", "root@example.com", "pw-12345-xyz")

    def test_registered(self):
        for m in (Challenge, SkillObjective, Solve, Submission, PracticeGroup, Membership):
            self.assertIn(m, admin.site._registry)

    def test_solve_and_submission_read_only(self):
        self.client.force_login(self.su)
        for m in (Solve, Submission):
            a = admin.site._registry[m]
            self.assertFalse(a.has_add_permission(None))
            self.assertFalse(a.has_change_permission(None))
            self.assertFalse(a.has_delete_permission(None))

    def test_changelists_render(self):
        make_challenge()
        self.client.force_login(self.su)
        for name in ("challenge", "skillobjective", "solve", "submission",
                     "practicegroup", "membership"):
            r = self.client.get(reverse(f"admin:ctf_{name}_changelist"))
            self.assertEqual(r.status_code, 200, name)
        r = self.client.get(reverse("admin:ctf_challenge_add"))
        self.assertEqual(r.status_code, 200)
        r = self.client.get(reverse("admin:accounts_user_change", args=[self.su.pk]))
        self.assertContains(r, "handle")
