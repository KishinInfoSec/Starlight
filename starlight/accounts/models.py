from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    email = models.EmailField(_("email address"))

    profile_public = models.BooleanField(default=False)
    handle = models.CharField(
        max_length=30, null=True, blank=True,
        validators=[RegexValidator(r"^[A-Za-z0-9_-]{3,30}\Z", "3-30 letters, digits, underscores or hyphens.")],
        help_text="Public display name for scoreboards and profiles. Unique, case-insensitive.",
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("handle"), condition=Q(handle__isnull=False),
                name="accounts_user_handle_ci_unique",
                violation_error_message=_("That handle is already taken."),
            ),
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                violation_error_message=_("An account with this email already exists."),
            ),
        ]
