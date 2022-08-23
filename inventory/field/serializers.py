from inventory.field.models import Field
from rest_framework import serializers


class FieldSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Field
        fields = ["id", "name", "retrival_value", "section"]
