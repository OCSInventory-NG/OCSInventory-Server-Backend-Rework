# OCSInventory-Server-Backend-Rework/user/models.py
from automation.rule.logic import Logic
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db import models
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()


class UserAuthProfile(models.Model):
    """
    User profile storing authentication metadata.
    """

    METHOD_CHOICES = [
        ("OIDC", "OIDC"),
        ("CAS", "CAS"),
        ("LDAP", "LDAP"),
        ("LOCAL", "LOCAL"),
        ("UNKNOWN", "UNKNOWN"),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_profile"
    )
    last_login_method = models.CharField(
        max_length=16, choices=METHOD_CHOICES, default="UNKNOWN"
    )
    last_login_backend = models.CharField(max_length=255, blank=True, null=True)
    last_login_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.last_login_method})"


def _infer_method_from_backend_path(backend_path: str | None) -> tuple[str, str | None]:
    """
    Map Django auth backend import path to a compact login method.
    """
    if not backend_path:
        return "UNKNOWN", None

    path_lower = backend_path.lower()
    if "oidc" in path_lower:
        return "OIDC", backend_path
    if "cas" in path_lower:
        return "CAS", backend_path
    if "ldap" in path_lower:
        return "LDAP", backend_path
    # fallback: local form auth or other custom backends
    return "LOCAL", backend_path


# user logged in signal
@receiver(user_logged_in, sender=User)
def user_login_handler(sender, user, request, **kwargs):
    """
    Signal handler for user login:
    - Detect the authentication backend/method
    - Persist it in UserAuthProfile
    - Attach a transient attribute on `user` so rules can read it
    - Run rule engine on 'user_login'
    """
    backend_path = getattr(user, "backend", None) or getattr(
        getattr(request, "session", {}), "_auth_user_backend", None
    )
    method, backend_path = _infer_method_from_backend_path(backend_path)

    profile, _ = UserAuthProfile.objects.get_or_create(user=user)
    profile.last_login_method = method
    profile.last_login_backend = backend_path
    profile.last_login_at = timezone.now()
    profile.save(
        update_fields=["last_login_method", "last_login_backend", "last_login_at"]
    )

    setattr(user, "login_method", method)

    if not getattr(user, "processed", False):
        logic = Logic("user_login", user)
        user = logic.process_rules()
