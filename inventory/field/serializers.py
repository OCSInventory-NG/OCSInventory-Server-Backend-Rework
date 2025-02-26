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
            "retrival_value",
            "override_target",
            "new_target",
            "retrival_method",
            "retrival_output",
            "section",
            "options",
        ]
        expandable_fields = {
        }
