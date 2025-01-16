from asset.inventory_section.models import InventorySection
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class InventorySectionSerializer(ExpandableSerializer):
    """
    Serializer class for InventorySection

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventorySection
        fields = [
            "id",
            "base",
            "template_section",
            "fields",
        ]

        expandable_fields = {
            "fields": "asset.inventory_field.serializers.InventoryFieldSerializer",
        }
