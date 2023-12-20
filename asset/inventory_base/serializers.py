from asset.inventory_base.models import InventoryBase
from asset.inventory_section.serializers import InventorySectionSerializer

from rest_framework import serializers


class InventoryBaseSerializer(serializers.ModelSerializer):
    """
    Serializer class for Base

    Args:
        serializers ([ModelSerializer])
    """

    # OS name constant that will determine the template
    OS_WIN = "windows"
    OS_LIN = "linux"
    OS_MAC = "mac"

    inventory_sections = InventorySectionSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventoryBase
        fields = [
            "id",
            "name",
            "description",
            "serial",
            "osname",
            "osversion",
            "uuid",
            "srcip",
            "srcmac",
            "domain",
            "template",
            "last_update",
            "inventory_sections",
        ]
        extra_kwargs = {"last_update": {"read_only": True}}

        http_method_names = ["get", "post", "patch", "delete"]
