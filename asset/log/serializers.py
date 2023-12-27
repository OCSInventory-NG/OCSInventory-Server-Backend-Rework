from asset.log.models import Log
from rest_framework import serializers


class LogSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Log
        fields = [
            "id",
            "asset",
            "timestamp",
            "scope",
            "comment",
        ]
        extra_kwargs = {"timestamp": {"read_only": True}}
        http_method_names = ["get", "post"]
