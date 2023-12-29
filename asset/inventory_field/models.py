from django.db import models

from asset.inventory_section.models import InventorySection
from inventory.field.models import Field


class InventoryField(models.Model):
    """
    InventoryField model class

    Contains the following fields:
        - inventory_section: link to related InventorySection
        - template_field: link to the related Template's Field
        - value: value of the field
    """

    inventory_section = models.ForeignKey(InventorySection,
                                          related_name='fields',
                                          on_delete=models.CASCADE)
    template_field = models.ForeignKey(Field, on_delete=models.CASCADE)
    value = models.CharField(max_length=255, blank=True, null=True)
