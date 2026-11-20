from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User


class UserFieldTests(TestCase):
    def mk(self, name, **kw):
        return User.objects.create_user(name, f"{name}@example.com", "pw-12345-xyz", **kw)

    def test_defaults(self):
        u = self.mk("a")
        self.assertFalse(u.profile_public)
        self.assertIsNone(u.handle)

    def test_many_null_handles_allowed(self):
        self.mk("a"); self.mk("b"); self.mk("c")

    def test_handle_case_insensitive_unique(self):
        self.mk("a", handle="Neo")
        with self.assertRaises(IntegrityError):
            self.mk("b", handle="nEO")

    def test_handle_format_validated(self):
        u = self.mk("a")
        for bad in ["ab", "has space", "x" * 31, "a@b"]:
            u.handle = bad
            with self.assertRaises(ValidationError, msg=bad):
                u.full_clean(exclude=["password"])
        u.handle = "ok_name-1"
        u.full_clean(exclude=["password"])
