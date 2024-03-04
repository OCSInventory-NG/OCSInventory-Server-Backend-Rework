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
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
