from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer
from asset.inventory_base.serializers import InventoryBaseSerializer
from .models import AssetGroup


class AssetGroupSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    Serializer class for AssetGroup
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AssetGroup
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
        expandable_fields = {}
