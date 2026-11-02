"""A change of the CPE thresholds matches Windows and macOS software again."""

from config.models import Config
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from security import config as security_config


@receiver(pre_save, sender=Config)
def remember_thresholds(sender, instance, **kwargs):
    if instance.name == security_config.SECTION:
        instance._security_thresholds = security_config.current().thresholds


@receiver(post_save, sender=Config)
def rematch_on_new_thresholds(sender, instance, **kwargs):
    if instance.name != security_config.SECTION:
        return
    before = getattr(instance, "_security_thresholds", None)
    if before is not None and security_config.current().thresholds != before:
        from inventory.software_identity.services import IdentityService

        IdentityService.rematch_cpe()
