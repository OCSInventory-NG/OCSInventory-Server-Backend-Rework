from rest_framework import serializers
from asset.inventory.models import InventorySection, InventoryField

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
            
            
class InventorySectionSerializer(serializers.ModelSerializer):
    """
    Serializer class for InventorySection

    Args:
        serializers ([ModelSerializer])
    """

    fields = InventoryFieldSerializer(many=True)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventorySection
        fields = [
            "id",
            "base",
            "template_section",
            "fields"
        ]



