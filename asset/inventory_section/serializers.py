from rest_framework import serializers

from asset.inventory_field.serializers import InventoryFieldSerializer
from asset.inventory_section.models import InventorySection


class InventorySectionSerializer(serializers.ModelSerializer):
    """
    Serializer class for InventorySection

    Args:
        serializers ([ModelSerializer])
    """

    fields = InventoryFieldSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventorySection
        fields = [
            "id",
            "base",
            "template_section",
            "fields"
        ]
