from django.db import models

from inventory.section.models import Section
from asset.inventory_base.models import InventoryBase

class InventorySection(models.Model):
    """
    InventorySection model class

    Contains the following fields:
        - base: link to the Base asset (device)
        - template_section: link to the related Template's Section
    """
    base = models.ForeignKey(InventoryBase, related_name='inventory_sections', on_delete=models.CASCADE)
    template_section = models.ForeignKey(Section, on_delete=models.CASCADE)
