from asset.inventory_base.models import InventoryBase
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


class SoftwareMapping(models.Model):
    """map software fields to template fields"""

    template = models.ForeignKey(
        Template,
        related_name="software_mappings",
        on_delete=models.CASCADE,
    )
    section = models.ForeignKey(
        Section,
        related_name="software_mappings",
        on_delete=models.CASCADE,
    )
    name = models.ForeignKey(
        Field,
        related_name="software_name_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    publisher = models.ForeignKey(
        Field,
        related_name="software_publisher_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    version = models.ForeignKey(
        Field,
        related_name="software_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    major_version = models.ForeignKey(
        Field,
        related_name="software_major_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    minor_version = models.ForeignKey(
        Field,
        related_name="software_minor_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    patch_version = models.ForeignKey(
        Field,
        related_name="software_patch_version_mappings",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )


class SoftwareDictionary(models.Model):
    """Aggregate which assets have a specific software signature"""

    name = models.TextField(blank=True, null=True)
    publisher = models.TextField(blank=True, null=True)
    version = models.CharField(max_length=128, blank=True, null=True)
    major_version = models.CharField(max_length=64, blank=True, null=True)
    minor_version = models.CharField(max_length=64, blank=True, null=True)
    patch_version = models.CharField(max_length=64, blank=True, null=True)
    assets = models.ManyToManyField(
        InventoryBase,
        related_name="software_dictionary_entries",
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    installation_number = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["publisher"]),
            models.Index(fields=["version"]),
        ]

@receiver(m2m_changed, sender=SoftwareDictionary.assets.through)
def assets_changed(sender, instance, action, **kwargs):
    """
    Update the 'installation_number' field when assets change.
    """
    if action in ["post_add", "post_remove"]:
        instance.installation_number = instance.assets.count()
        instance.save(update_fields=['installation_number'])
