from django.contrib.auth import get_user_model
from django.utils import timezone

from ctf.models import Challenge

GOOD_HMAC = "a" * 64


def make_user(name="u1"):
    return get_user_model().objects.create_user(name, f"{name}@example.com", "pw-12345-xyz")


def make_challenge(slug="c1", **kw):
    data = dict(slug=slug, title=slug, category="crypto", difficulty="beginner", points=10,
                description="# hi", pub_date=timezone.now(), flag_hmac=GOOD_HMAC)
    data.update(kw)
    return Challenge.objects.create(**data)
