from asset.inventory_base.models import InventoryBase
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer
from inventory.template.serializers import TemplateSerializer


class InventoryBaseSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    Serializer class for Base
    """

    # OS name constant that will determine the template
    OS_WIN = "windows"
    OS_LIN = "linux"
    OS_MAC = "mac"

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
        ]

        expandable_fields = {
            "template": TemplateSerializer,
        }
        extra_kwargs = {"last_update": {"read_only": True}}
        http_method_names = ["get", "post", "patch", "delete"]
