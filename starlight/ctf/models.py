from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

HEX64 = RegexValidator(r"^[0-9a-f]{64}\Z", "Must be 64 lowercase hex characters.")


class SkillObjective(models.Model):
    framework = models.CharField(max_length=50)
    code = models.CharField(max_length=50)
    title = models.CharField(max_length=200)

    class Meta:
        db_table = "ctf_skillobjective"
        ordering = ["framework", "code"]
        constraints = [
            models.UniqueConstraint(fields=["framework", "code"], name="ctf_unique_skill_per_framework"),
        ]

    def __str__(self):
        return f"{self.framework} {self.code}"


class Challenge(models.Model):
    class Category(models.TextChoices):
        WEB = "web", "Web"
        CRYPTO = "crypto", "Cryptography"
        FORENSICS = "forensics", "Forensics"
        REVERSING = "reversing", "Reverse engineering"
        PWN = "pwn", "Binary exploitation"
        OSINT = "osint", "OSINT"
        MISC = "misc", "Miscellaneous"

    class Difficulty(models.TextChoices):  # declaration order is beginner-first
        BEGINNER = "beginner", "Beginner"
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.BEGINNER)
    points = models.PositiveIntegerField()
    description = models.TextField(help_text="Markdown.")
    pub_date = models.DateTimeField("date published")
    flag_hmac = models.CharField(
        max_length=64, validators=[HEX64],
        help_text="HMAC-SHA256 of the normalized flag, hex. Never the flag itself.",
    )
    external_url = models.URLField(blank=True)
    related_quiz = models.ForeignKey(
        "quizzes.Quiz", null=True, blank=True, on_delete=models.SET_NULL, related_name="challenges",
    )
    skills = models.ManyToManyField(
        SkillObjective, blank=True, related_name="challenges", db_table="ctf_challenge_skills",
    )

    class Meta:
        db_table = "ctf_challenge"
        ordering = ["-pub_date"]

    def __str__(self):
        return self.title


class ChallengeFile(models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="files")
    r2_key = models.CharField(max_length=500, unique=True)
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, validators=[HEX64])

    class Meta:
        db_table = "ctf_challengefile"
        ordering = ["filename"]

    def __str__(self):
        return self.filename


class Solve(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ctf_solves")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="solves")
    solved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ctf_solve"
        ordering = ["-solved_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "challenge"], name="ctf_unique_solve_per_user_challenge"),
        ]

    def __str__(self):
        return f"{self.user} solved {self.challenge}"


class Submission(models.Model):
    """An attempt. Deliberately stores no submitted text."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ctf_submissions")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="submissions")
    correct = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ctf_submission"
        ordering = ["-created", "-id"]

    def __str__(self):
        return f"{self.user} -> {self.challenge} ({'ok' if self.correct else 'no'})"


class PracticeGroup(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    invite_code = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_practice_groups")

    class Meta:
        db_table = "ctf_practicegroup"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="practice_memberships")
    group = models.ForeignKey(PracticeGroup, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ctf_membership"
        ordering = ["joined", "id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "group"], name="ctf_unique_membership_per_user_group"),
        ]

    def __str__(self):
        return f"{self.user} in {self.group}"
