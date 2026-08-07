from importlib import import_module

from auth.auth_method.models import AuthMethod
from django.conf import settings
from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete
from django.dispatch import receiver
from ocsinventory_backend.ocs_framework.crypto import decrypt, encrypt


def get_sensitive_config_fields():
    """
    Collect the sensitive config field names declared by the auth backends.

    Backends are imported lazily because they import this module, and a backend
    without the static method simply declares no secret.
    """
    fields = set()
    for backend_path in settings.OCS_CUSTOM_AUTH_BACKENDS.values():
        module_name, class_name = backend_path.rsplit(".", 1)
        backend_class = getattr(import_module(module_name), class_name)
        getter = getattr(backend_class, "get_sensitive_config_fields", None)
        if getter is not None:
            fields.update(getter())
    return fields


class AuthConfig(models.Model):
    """
    AuthConfig model class definition

    Fields :
    - Auth method
    - JSON config
    - Priority (two enabled configs for the same auth_method
    cannot have the same priority)
    - Enabled
    """

    auth_method = models.ForeignKey(
        AuthMethod, related_name="configs", on_delete=models.CASCADE, null=True
    )
    name = models.CharField(max_length=255, default="Default Config Name")
    description = models.TextField(blank=True, null=True)
    config = models.JSONField()
    priority = models.IntegerField(blank=True, null=True)
    enabled = models.BooleanField(default=False)

    def _map_sensitive_values(self, func):
        """Return a copy of config with func applied to the sensitive values."""
        if not isinstance(self.config, dict):
            return self.config
        sensitive_fields = get_sensitive_config_fields()
        return {
            key: func(value) if key in sensitive_fields else value
            for key, value in self.config.items()
        }

    @classmethod
    def from_db(cls, db, field_names, values):
        """Decrypt the secrets so that config always holds clear text in Python."""
        instance = super().from_db(db, field_names, values)
        instance.config = instance._map_sensitive_values(decrypt)
        return instance

    def save(self, *args, **kwargs):
        """
        Encrypt the secrets for storage only.

        The clear text config is restored afterwards so the instance stays
        usable by the caller.
        """
        clear_config = self.config
        self.config = self._map_sensitive_values(encrypt)
        try:
            super().save(*args, **kwargs)
        finally:
            self.config = clear_config


@receiver(post_delete, sender=AuthConfig)
def adjust_priorities_on_delete(sender, instance, **kwargs):
    """
    This signal is triggered when an AuthConfig is deleted (SSO or non-SSO).
    Given that SSO configs have a priority of None, the signal is triggered but the
    logic will not be applied.

    For non-SSO configs, the logic is as follows:
    After a config is deleted, adjust the priorities of remaining configs.
    The logic is to decrement the priority of all configs that had a higher priority
    than the deleted config.
    """
    # if origin is AuthMethod, do not trigger the signal (nested deletion,
    # all configs will be deleted at the same time and the signal will raise
    # a DoesNotExist exception when trying to decrement the priority of a config)
    if isinstance(kwargs.get("origin"), AuthMethod):
        return

    configs_higher_priority = AuthConfig.objects.filter(
        auth_method=instance.auth_method,
        priority__gt=instance.priority if instance.priority else 0,
    )

    # decrement their priorities
    configs_higher_priority.update(priority=F("priority") - 1)
