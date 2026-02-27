import logging

from automation.rule.logic import Logic
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from inventory.template.models import Template


# Create your models here.
class InventoryBase(models.Model):
    """
    Asset's base model class definition

    The model will contain the following info
    - Name
    - Description
    - Serial
    - OS Name
    - OS Version
    - UUID
    - SRCIP
    - SRCMAC
    - Template
    - Domain
    - is_template_forced
    """

    name = models.CharField(max_length=50, null=False)
    description = models.CharField(max_length=255, null=True)
    serial = models.CharField(max_length=255)
    osname = models.CharField(max_length=255, null=False)
    osversion = models.CharField(max_length=255, blank=True)
    uuid = models.CharField(max_length=255, null=False, unique=True)
    srcip = models.CharField(max_length=255, blank=True)
    srcmac = models.CharField(max_length=255, blank=True)
    domain = models.CharField(max_length=255, blank=True)
    agent = models.CharField(max_length=255, blank=True)
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, blank=True, null=True
    )
    is_template_forced = models.BooleanField(default=False)
    accountinfo = GenericRelation(
        "accountinfo.AccountinfoData",
        content_type_field="content_type",
        object_id_field="object_id",
    )
    last_update = models.DateTimeField(auto_now=True)


@receiver(post_save, sender=InventoryBase)
def inventory_received_handler(sender, instance, created, **kwargs):
    logger = logging.getLogger(__name__)
    # manually assigned > auto assigned
    if instance.is_template_forced:
        # skip auto os based template assignment logic
        logger.debug(
            f"Template is manually assigned for ID {instance.id}, "
            "skipping inventory_received Rules."
        )
        return

    if not getattr(instance, "processed", False):
        logger.debug(f"Running inventory_received Rules for ID {instance.id}.")
        logic = Logic("inventory_received", instance)
        instance = logic.process_rules()


@receiver(pre_delete, sender=InventoryBase)
def inventory_delete_capture_dictionary_entries(sender, instance, **kwargs):
    # get links before jjango removes m2M relations during deletion
    instance._software_dictionary_ids = list(
        instance.software_dictionary_entries.values_list("id", flat=True)
    )


@receiver(post_delete, sender=InventoryBase)
def inventory_delete_cleanup_dictionary_entries(sender, instance, **kwargs):
    entry_ids = getattr(instance, "_software_dictionary_ids", [])
    if not entry_ids:
        return

    logger = logging.getLogger(__name__)
    try:
        from inventory.software.services import SoftwareDictionaryService

        SoftwareDictionaryService.cleanup_delete(instance.id, entry_ids)
    except Exception as exc:
        logger.exception(
            "Failed to cleanup software dictionary after deleting asset %s: %s",
            getattr(instance, "id", "unknown"),
            exc,
        )
