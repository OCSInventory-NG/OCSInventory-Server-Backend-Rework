from deployment.result.models import Result
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer

class ResultSerializer(ExpandableSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

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
            'package': 'deployment.package.serializers.PackageSerializer',
            'asset': 'asset.inventory_base.serializers.InventoryBaseSerializer',
            'group': 'asset.asset_group.serializers.AssetGroupSerializer',
        }

        extra_kwargs = {"package": {"required": False}}
