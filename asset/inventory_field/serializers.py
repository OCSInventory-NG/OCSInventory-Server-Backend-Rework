from rest_framework import serializers
from asset.inventory_field.models import InventoryField


class InventoryFieldSerializer(serializers.ModelSerializer):
    """
    Serializer class for InventoryField

    Args:
        serializers ([ModelSerializer])
    """

    field_name = serializers.SerializerMethodField()

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventoryField
        fields = [
            "id",
            "inventory_section",
            "template_field",
            "field_name",
            "value"
        ]

    def get_field_name(self, obj):
        """Return the field name"""
        return obj.template_field.name
