from automation.rule.logic import Logic
from django.contrib.auth.models import Group, User
from django.contrib.auth.signals import user_logged_in
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.dispatch import receiver


class UserGroupAssignment(models.Model):
    SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("ldap", "LDAP"),
        ("rule", "Rule"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_group_assignments",
    )
    source_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_object = GenericForeignKey("source_content_type", "source_object_id")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group", "source"],
                name="uniq_user_group_source_assignment",
            )
        ]
        indexes = [
            models.Index(fields=["user", "source"], name="idx_assignment_user_source"),
        ]


# user logged in signal
@receiver(user_logged_in, sender=User)
def user_login_handler(sender, user, request, **kwargs):
    """
    Signal handler for user login.
    """
    if not getattr(user, "processed", False):
        logic = Logic("user_login", user)
        logic.process_rules()
