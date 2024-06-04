from automation.rule.logic import Logic
from django.db import models
from django.db.models.signals import post_save
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
    """

    name = models.CharField(max_length=50, null=False)
    description = models.CharField(max_length=255)
    serial = models.CharField(max_length=255)
    osname = models.CharField(max_length=255, null=False)
    osversion = models.CharField(max_length=255, null=False)
    uuid = models.CharField(max_length=255, null=False, unique=True)
    srcip = models.CharField(max_length=255)
    srcmac = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, blank=True, null=True
    )
    last_update = models.DateTimeField(auto_now=True)


@receiver(post_save, sender=InventoryBase)
def inventory_received_handler(sender, instance, created, **kwargs):
    if not getattr(instance, "processed", False):
        logic = Logic("inventory_received", instance)
        instance = logic.process_rules()
