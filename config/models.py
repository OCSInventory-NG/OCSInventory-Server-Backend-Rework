import logging

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from ocsinventory_backend.ocs_framework.logging_handlers import DynamicLogLevelHandler


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
    """Update dynamic log level handlers when the server configuration changes"""
    logging.debug("handle_config_change triggered with instance: %s", instance)
    if instance.name != "server":
        return

    try:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, DynamicLogLevelHandler):
                handler._update_level()
    except Exception as e:
        logging.error(f"Failed to update log level: {e}")
