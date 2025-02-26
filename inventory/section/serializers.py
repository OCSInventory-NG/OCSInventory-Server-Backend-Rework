from inventory.section.models import Section
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer
from inventory.field.serializers import FieldSerializer

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
            "retrival_method",
            "retrival_output",
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
