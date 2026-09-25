from django.db import models
from ocsinventory_backend.ocs_framework.models import RestrictVisibility


class VirtualCol(RestrictVisibility):
    """
    Virtual column model class definition

    The model will contain the following info
    - Name (the column header, i.e. "BIOS NAME")
    - Target (the table the column belongs to)
    - Mapping, {"<template id>": <field id>}
    """

    TARGET_CHOICES = (("asset", "Assets"),)

    name = models.CharField(max_length=100)
    target = models.CharField(max_length=30, choices=TARGET_CHOICES, default="asset")
    mapping = models.JSONField(default=dict)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        """Define the default ordering"""

        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def key(self):
        """Identify the column in listings, a name may be shared or collide"""
        return f"vc_{self.pk}"

    def field_ids(self):
        """Return the Field ids this column reads, whatever the template"""
        return [int(field_id) for field_id in self.mapping.values() if field_id]
