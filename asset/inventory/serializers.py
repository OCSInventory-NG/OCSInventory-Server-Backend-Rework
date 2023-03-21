from asset.inventory.models import Inventory
from inventory.template.models import Template
from rest_framework import serializers
import json


class InventorySerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    # OS name constant that will determine the template
    OS_WIN = "windows"
    OS_LIN = "linux"
    OS_MAC = "mac"

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Inventory
        fields = [
            "id",
            "assetId",
            "sectionId",
            "sectionName",
            "sectionJson",
        ]
        http_method_names = ["get", "post", "patch", "delete"]

    def create(self, validated_data):
        """
        Override existing create method to set the template link

        Args:
            validated_data : POST request

        Returns:
            [Inventory] object
        """
        
        try:
            jsonAsset = validated_data['sectionJson']
            if isinstance(jsonAsset, str):
                jsonAsset = json.loads(jsonAsset)
            id = jsonAsset['ID']['DEVICEID']

            assetInventory = Inventory(assetId=id)
            assetInventory.save()

            for key in jsonAsset:
                print(key)
                if key != "ID":
                    subAsset = Inventory(sectionId=assetInventory, sectionJson=jsonAsset[key], sectionName=key)
                    subAsset.save()
        except IndexError:
            print("An error happenned")

        return assetInventory
