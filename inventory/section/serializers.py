from inventory.field.serializers import FieldExportSerializer, FieldSerializer
from inventory.section.models import Section
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class SectionSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    fields = FieldSerializer(many=True, read_only=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Section
        fields = [
            "id",
            "name",
            "retrieval_method",
            "retrieval_output",
            "target",
            "template",
            "fields",
            "options",
        ]

        expandable_fields = {
            "fields": FieldSerializer,
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        if "fields" in validated_data.keys():
            # If fields are present
            fields = validated_data.pop("fields")
            parent = super().create(validated_data)

            for field in fields:
                field["section"] = parent
            self.fields["fields"].create(fields)
        else:
            parent = super().create(validated_data)

        return parent


class SectionExportSerializer(ModelSerializer):
    """
    Export serializer for Section, ids and fk relations are not included
    Nested values will always be expanded (no ExpandableFieldsMixin)
    """

    fields = FieldExportSerializer(many=True, read_only=False)

    class Meta:
        model = Section
        fields = ["name", "target", "fields"]
