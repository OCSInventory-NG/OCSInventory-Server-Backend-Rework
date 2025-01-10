from accountinfo.models import AccountinfoConfig, AccountinfoValue, AccountinfoData
from accountinfo.serializers import (
    AccountinfoConfigSerializer,
    AccountinfoValueSerializer,
    AccountinfoDataSerializer,
)
from asset.inventory_base.models import InventoryBase
from rest_framework import serializers
import json


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

        if accountinfo and accountinfo.lower() == "true":
            config = AccountinfoConfig.objects.all()
            serialized_config = AccountinfoConfigSerializer(config, many=True).data
            config_mapping = {item["id"]: item["name"] for item in serialized_config}

            values = AccountinfoValue.objects.all()
            serialized_values = AccountinfoValueSerializer(values, many=True).data
            values_mapping = {item["id"]: item["value"] for item in serialized_values}

            data = AccountinfoData.objects.filter(object_id=representation["id"])

            if not data:
                return representation

            serialized_data = AccountinfoDataSerializer(data, many=True).data
            accountdata_only = [item["accountdata"] for item in serialized_data]

            accountdata_with_names = {
                config_mapping.get(int(key), key): value
                for (key, value) in accountdata_only[0].items()
            }

            account_data = {}
            for key, value in accountdata_with_names.items():
                if isinstance(value, dict):
                    account_data[key] = value["text"]
                elif isinstance(value, list):
                    value_transform = ""
                    for index, val in enumerate(value):
                        value_transform = value_transform + values_mapping.get(
                            int(val), val
                        )
                        if index + 1 < len(value):
                            value_transform = value_transform + ", "
                    account_data[key] = value_transform
                else:
                    account_data[key] = value
            representation["accountinfo"] = account_data

        return representation
