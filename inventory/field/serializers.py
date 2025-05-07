from inventory.field.models import Field
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class FieldSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Field
        fields = [
            "id",
            "name",
            "order",
            "retrival_value",
            "override_target",
            "new_target",
            "retrival_method",
            "retrival_output",
            "section",
            "options",
            "default_visibility"
        ]
        expandable_fields = {}
        
    def create(self, validated_data):
        """
        Overriding the create method to manage field order.
        """
        validated_data["order"] = (
            Field.objects.filter(section=validated_data["section"]).count()
            + 1
        )
        return super().create(validated_data)
