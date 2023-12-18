from django.db import models

from asset.base.models import Base
from inventory.section.models import Section
from inventory.field.models import Field

class InventorySection(models.Model):
    """
    InventorySection model class

    Contains the following fields:
        - base: link to the Base asset (device)
        - template_section: link to the related Template's Section
    """
    base = models.ForeignKey(Base, related_name='inventory_sections', on_delete=models.CASCADE)
    template_section = models.ForeignKey(Section, on_delete=models.CASCADE)

class InventoryField(models.Model):
    """
    InventoryField model class

    Contains the following fields:
        - inventory_section: link to related InventorySection
        - template_field: link to the related Template's Field
        - value: value of the field
    """

    inventory_section = models.ForeignKey(InventorySection, related_name='fields', on_delete=models.CASCADE)
    template_field = models.ForeignKey(Field, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)
