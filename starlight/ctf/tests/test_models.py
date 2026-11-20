from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from ctf.models import (Challenge, ChallengeFile, Membership, PracticeGroup,
                        SkillObjective, Solve, Submission)
from .helpers import GOOD_HMAC, make_challenge, make_user


class ChallengeTests(TestCase):
    def test_slug_unique(self):
        make_challenge("a")
        with self.assertRaises(IntegrityError):
            make_challenge("a")

    def test_flag_hmac_validation(self):
        c = make_challenge()
        for bad in ["", "abc", "A" * 64, "g" * 64, "a" * 63, "a" * 65]:
            c.flag_hmac = bad
            with self.assertRaises(ValidationError, msg=bad):
                c.full_clean()
        c.flag_hmac = GOOD_HMAC
        c.full_clean()

    def test_optional_fields_and_quiz_set_null(self):
        from quizzes.models import Quiz, Topic
        from django.utils import timezone
        quiz = Quiz.objects.create(topic=Topic.objects.create(name="t", slug="t"), title="q",
                                   slug="q", pub_date=timezone.now())
        c = make_challenge(related_quiz=quiz)
        quiz.delete()
        c.refresh_from_db()
        self.assertIsNone(c.related_quiz)
        self.assertEqual(c.external_url, "")

    def test_difficulty_choices_beginner_first(self):
        self.assertEqual(Challenge.Difficulty.values[0], "beginner")

    def test_skills_m2m(self):
        c = make_challenge()
        s = SkillObjective.objects.create(framework="sec+", code="1.1", title="x")
        c.skills.add(s)
        self.assertEqual(list(c.skills.all()), [s])

    def test_db_table_names(self):
        self.assertEqual(Challenge._meta.db_table, "ctf_challenge")
        self.assertEqual(Challenge.skills.through._meta.db_table, "ctf_challenge_skills")


class SkillObjectiveTests(TestCase):
    def test_unique_framework_code(self):
        SkillObjective.objects.create(framework="sec+", code="1.1", title="a")
        SkillObjective.objects.create(framework="net+", code="1.1", title="a")
        with self.assertRaises(IntegrityError):
            SkillObjective.objects.create(framework="sec+", code="1.1", title="b")


class ChallengeFileTests(TestCase):
    def test_r2_key_unique(self):
        c = make_challenge()
        kw = dict(challenge=c, filename="f", size=1, sha256="b" * 64)
        ChallengeFile.objects.create(r2_key="k", **kw)
        with self.assertRaises(IntegrityError):
            ChallengeFile.objects.create(r2_key="k", **kw)

    def test_sha256_validated(self):
        f = ChallengeFile(challenge=make_challenge(), r2_key="k", filename="f", size=1, sha256="zz")
        with self.assertRaises(ValidationError):
            f.full_clean()


class SolveSubmissionTests(TestCase):
    def test_solve_unique_per_user_challenge(self):
        u, c = make_user(), make_challenge()
        Solve.objects.create(user=u, challenge=c)
        with self.assertRaises(IntegrityError), transaction.atomic():  # savepoint for the test txn only
            Solve.objects.create(user=u, challenge=c)
        Solve.objects.create(user=make_user("u2"), challenge=c)

    def test_solved_at_auto(self):
        s = Solve.objects.create(user=make_user(), challenge=make_challenge())
        self.assertIsNotNone(s.solved_at)

    def test_submission_allows_repeats_and_stores_no_text(self):
        u, c = make_user(), make_challenge()
        Submission.objects.create(user=u, challenge=c, correct=False)
        Submission.objects.create(user=u, challenge=c, correct=False)
        names = {f.name for f in Submission._meta.get_fields()}
        self.assertEqual(names, {"id", "user", "challenge", "correct", "created"})


class GroupTests(TestCase):
    def test_slug_and_invite_unique(self):
        o = make_user()
        PracticeGroup.objects.create(name="a", slug="a", invite_code="i1", owner=o)
        with self.assertRaises(IntegrityError), transaction.atomic():  # savepoint for the test txn only
            PracticeGroup.objects.create(name="b", slug="a", invite_code="i2", owner=o)
        with self.assertRaises(IntegrityError):
            PracticeGroup.objects.create(name="c", slug="c", invite_code="i1", owner=o)

    def test_membership_unique_and_roles(self):
        o = make_user()
        g = PracticeGroup.objects.create(name="a", slug="a", invite_code="i1", owner=o)
        m = Membership.objects.create(user=o, group=g, role=Membership.Role.OWNER)
        self.assertIsNotNone(m.joined)
        with self.assertRaises(IntegrityError):
            Membership.objects.create(user=o, group=g)
        self.assertEqual(Membership(user=o, group=g).role, "member")
