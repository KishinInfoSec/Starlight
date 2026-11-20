import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone

from quizzes.models import Option, Question, Quiz, Topic

PASSWORD = "S3cure-pass-phrase"


def create_user(username):
    return get_user_model().objects.create_user(username, f"{username}@example.com", PASSWORD)


def create_topic(name="Networking", slug=None):
    return Topic.objects.create(name=name, slug=slug or name.lower().replace(" ", "-"))


def create_quiz(topic, title="Ports 101", days=-1, slug=None):
    """`days` offset from now: negative = published, positive = future."""
    return Quiz.objects.create(
        topic=topic, title=title, slug=slug or title.lower().replace(" ", "-"),
        pub_date=timezone.now() + datetime.timedelta(days=days),
    )


def add_question(quiz, text="Which port does HTTPS use?", options=(("443", True), ("80", False)),
                 explanation="", order=0):
    q = Question.objects.create(quiz=quiz, text=text, explanation=explanation, order=order)
    for opt_text, correct in options:
        Option.objects.create(question=q, text=opt_text, is_correct=correct)
    return q
