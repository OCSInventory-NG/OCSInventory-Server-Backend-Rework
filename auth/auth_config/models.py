from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db.models import F

from auth.auth_method.models import AuthMethod


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
        AuthMethod,
        related_name="configs",
        on_delete=models.CASCADE,
        null=True
    )
    name = models.CharField(max_length=255, default="Default Config Name")
    description = models.TextField(blank=True)
    config = models.JSONField()
    priority = models.IntegerField(blank=True, null=True)
    enabled = models.BooleanField(default=False)

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
    if isinstance(kwargs.get('origin'), AuthMethod):
        return

    configs_higher_priority = AuthConfig.objects.filter(
        auth_method=instance.auth_method,
        priority__gt=instance.priority if instance.priority else 0
    )

    # decrement their priorities
    configs_higher_priority.update(priority=F('priority') - 1)