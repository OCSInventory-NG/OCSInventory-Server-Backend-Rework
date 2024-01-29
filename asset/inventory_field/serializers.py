from rest_framework import serializers
from asset.inventory_field.models import InventoryField


class InventoryFieldSerializer(serializers.ModelSerializer):
    """
    Serializer class for InventoryField

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventoryField
        fields = [
            "id",
            "inventory_section",
            "template_field",
            "value"
        ]

