from rest_framework import serializers

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
        fields = ["id", "name", "description", "is_dynamic", "search", "assets"]
