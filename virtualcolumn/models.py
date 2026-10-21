from django.db import models
from ocsinventory_backend.ocs_framework.models import RestrictVisibility


class VirtualCol(RestrictVisibility):
    """
    Virtual column model class definition

    The model will contain the following info
    - Name (the column header, i.e. "BIOS VERSION")
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


class ColumnLayout(RestrictVisibility):
    """
    Column layout model class definition

    A named set of columns an admin saves for a listing, i.e. "Support view"

    The model will contain the following info
    - Name (shown in the layout picker, may be shared)
    - Target (the listing the layout applies to)
    - Columns, the ordered column keys ("name", "vc_3", ...)
    """

    name = models.CharField(max_length=100)
    target = models.CharField(
        max_length=30, choices=VirtualCol.TARGET_CHOICES, default="asset"
    )
    columns = models.JSONField(default=list)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        """Define the default ordering"""

        ordering = ["name"]

    def __str__(self):
        return self.name
