from django.conf import settings
from django.db import models
from django.db.models import Q


class Topic(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Quiz(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="quizzes")
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    pub_date = models.DateTimeField("date published")

    class Meta:
        ordering = ["-pub_date"]
        verbose_name_plural = "quizzes"

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    explanation = models.TextField(blank=True, help_text="Shown after the quiz is submitted.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:50]


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=200)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["question"], condition=Q(is_correct=True),
                name="quizzes_one_correct_option_per_question",
            ),
        ]

    def __str__(self):
        return self.text


class AttemptQuerySet(models.QuerySet):
    def completed(self):
        """Only attempts whose answers were fully written (flag is set last)."""
        return self.filter(completed=True)


class Attempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quiz_attempts")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    score = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    created = models.DateTimeField(auto_now_add=True)
    # Set True as the very last write; incomplete attempts are never shown or counted.
    completed = models.BooleanField(default=False)

    objects = AttemptQuerySet.as_manager()

    class Meta:
        ordering = ["-created", "-id"]

    def __str__(self):
        return f"{self.user} · {self.quiz} · {self.score}/{self.total}"

    @property
    def percent(self):
        return round(100 * self.score / self.total) if self.total else 0


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField()

    class Meta:
        ordering = ["question__order", "question__id"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "question"], name="quizzes_one_answer_per_question"),
        ]
