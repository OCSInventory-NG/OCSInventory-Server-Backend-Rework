from asset.inventory_base.models import InventoryBase
from rest_framework import serializers


class InventoryBaseSerializer(serializers.ModelSerializer):
    """
    Serializer class for Base

    Args:
        serializers ([ModelSerializer])
    """

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
        extra_kwargs = {"last_update": {"read_only": True}}

        http_method_names = ["get", "post", "patch", "delete"]

    def to_representation(self, instance):
        """
        Customize the representation to include additional fields
        based on the 'accountinfo' URL parameter.
        """
        representation = super().to_representation(instance)
        request = self.context.get("request")

        if request:
            accountinfo = request.query_params.get("accountinfo")
            if accountinfo == "true":
                # TODO: call les données administratives
                representation["extra_info"] = "Additional data for accountinfo"

        return representation
