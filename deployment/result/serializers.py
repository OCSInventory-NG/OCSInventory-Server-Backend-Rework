from asset.asset_group.models import AssetGroup
from asset.asset_group.serializers import AssetGroupSerializer
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from deployment.result.models import Result
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class ResultSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serializer class provides the API representation
    """

    # using primary key related field to avoid circular import
    asset = serializers.PrimaryKeyRelatedField(
        queryset=InventoryBase.objects.all(), allow_null=True
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=AssetGroup.objects.all(), allow_null=True
    )

    class Meta:
        model = Result
        fields = [
            "id",
            "package",
            "asset",
            "group",
            "name",
            "status",
            "comment",
            "date_created",
        ]

        expandable_fields = {
            "asset": InventoryBaseSerializer,
            "group": AssetGroupSerializer,
        }
        extra_kwargs = {"package": {"required": False}}
