from rest_framework import serializers
from django.core import serializers as ser
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from .models import AssetGroup


class AssetGroupSerializer(serializers.ModelSerializer):
    """
    Serializer class for AssetGroup

    Args:
        serializers ([ModelSerializer])
    """
    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AssetGroup
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['asset_bases'] = InventoryBaseSerializer(
            InventoryBase.objects.filter(id__in=ret["assets"]), many=True
        ).data

        return ret
