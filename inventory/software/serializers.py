from inventory.field.serializers import FieldSerializer
from inventory.section.serializers import SectionSerializer
from inventory.software.models import SOFTWARE_FIELD_KEYS, SoftwareMapping
from inventory.template.serializers import TemplateSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class SoftwareMappingSerializer(ExpandableFieldsMixin, ModelSerializer):
    """Expose mappings between fixed software fields and template fields"""

    class Meta:
        model = SoftwareMapping
        fields = [
            "id",
            "template",
            "template_field",
            "template_section",
            "field_name",
        ]

        expandable_fields = {
            "template": TemplateSerializer,
            "template_field": FieldSerializer,
            "template_section": SectionSerializer,
        }
