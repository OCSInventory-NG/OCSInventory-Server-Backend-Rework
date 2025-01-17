from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer

from .models import AssetGroup


class AssetGroupSerializer(ExpandableSerializer):
    """
    Serializer class for AssetGroup

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AssetGroup
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
        expandable_fields = {
            "assets": "asset.inventory_base.serializers.InventoryBaseSerializer",
        }
