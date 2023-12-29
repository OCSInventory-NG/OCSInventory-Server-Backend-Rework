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
    # adding section_name to the serializer
    section_name = serializers.SerializerMethodField()

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventorySection
        fields = [
            "id",
            "base",
            "template_section",
            "section_name",
            "fields",
        ]

    def get_section_name(self, obj):
        """Return the section name"""
        return obj.template_section.name
