from inventory.section.serializers import SectionExportSerializer, SectionSerializer
from inventory.template.models import Template
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class TemplateSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    sections = SectionSerializer(many=True, read_only=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Template
        fields = ["id", "name", "os", "is_protected", "last_update", "sections"]

        expandable_fields = {
            "sections": SectionSerializer,
        }
        extra_kwargs = {"last_update": {"read_only": True}}

    def create(self, validated_data):
        """Override create to allow nested creation of sections"""
        if "sections" in validated_data.keys():
            # If sections are present
            sections = validated_data.pop("sections")
            parent = super().create(validated_data)

            for section in sections:
                section["template"] = parent
            self.fields["sections"].create(sections)
        else:
            parent = super().create(validated_data)

        return parent


class TemplateExportSerializer(ModelSerializer):
    """
    Export serializer for Template, ids and fk relations are not included
    Nested values will always be expanded (no ExpandableFieldsMixin)
    """
    sections = SectionExportSerializer(many=True, read_only=False)

    class Meta:
        model = Template
        fields = ["name", "os", "is_protected", "sections"]
