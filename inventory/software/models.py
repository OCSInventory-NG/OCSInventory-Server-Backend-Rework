from django.db import models
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


SOFTWARE_FIELD_CHOICES = (
    ("name", "Name"),
    ("major_version", "Major version"),
    ("minor_version", "Minor version"),
    ("patch_version", "Patch version"),
    ("publisher", "Publisher"),
    ("language", "Language"),
    ("size", "Size"),
    ("install_date", "Install date"),
    ("install_location", "Install location"),
)


class SoftwareFieldMapping(models.Model):
    """Map fixed software fields to template specific inventory fields"""

    template = models.ForeignKey(
        Template, related_name="software_field_mappings", on_delete=models.CASCADE
    )
    template_section = models.ForeignKey(Section,
        related_name="software_mappings",
        on_delete=models.CASCADE
    )
    template_field = models.ForeignKey(
        Field, related_name="software_mappings", on_delete=models.CASCADE
    )
    field_name = models.CharField(max_length=64, choices=SOFTWARE_FIELD_CHOICES)
