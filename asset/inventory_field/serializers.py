from asset.inventory_field.models import InventoryField
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class InventoryFieldSerializer(ExpandableSerializer):
    """
    Serializer class for InventoryField

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventoryField
        fields = ["id", "inventory_section", "template_field", "value"]
