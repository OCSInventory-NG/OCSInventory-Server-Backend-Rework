from deployment.result.models import Result
from rest_framework import serializers


class ResultSerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
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
        extra_kwargs = {"package": {"required": False}}
