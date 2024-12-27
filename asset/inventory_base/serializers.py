from accountinfo.models import AccountinfoConfig, AccountinfoData
from accountinfo.serializers import (
    AccountinfoConfigSerializer,
    AccountinfoDataSerializer,
)
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
        accountinfo = request.query_params.get("accountinfo")
        data = AccountinfoData.objects.filter(object_id=representation["id"])

        if not request or accountinfo == "false" or not data:
            return representation

        else:
            config = AccountinfoConfig.objects.all()
            serialized_config = AccountinfoConfigSerializer(config, many=True).data
            config_mapping = {item["id"]: item["name"] for item in serialized_config}

            serialized_data = AccountinfoDataSerializer(data, many=True).data
            accountdata_only = [item["accountdata"] for item in serialized_data]

            accountdata_with_names = {
                config_mapping.get(int(key), key): value
                for (key, value) in accountdata_only[0].items()
            }

            representation["accountinfo"] = accountdata_with_names

            return representation
