from rest_framework import serializers
from deployment.result.models import Result


class ResultSerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Result
        fields = ["id", "package", "name", "check_action", "result", "date_created"]
        extra_kwargs = {"package": {"required": False}}
