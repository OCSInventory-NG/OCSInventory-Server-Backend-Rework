from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from ocsinventory_backend.ocs_framework.logmanager import DynamicLogLevelManager


class Config(models.Model):
    """[summary]

    Args:
        models ([type]): [description]
    """

    class Meta:
        ordering = ["name"]

    name = models.CharField(max_length=100, primary_key=True)
    value = models.JSONField()


@receiver(post_save, sender=Config)
def handle_config_change(sender, instance, **kwargs):
    if instance.name == "server":
        DynamicLogLevelManager()
