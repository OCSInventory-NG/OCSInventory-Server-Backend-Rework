from rest_framework import serializers
from deployment.history.models import History


class HistorySerializer(serializers.ModelSerializer):
    """
    This serializer class provides the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = History
        fields = ["id", "package", "asset", "date_assigned", "status"]
        extra_kwargs = {"status": {"required": False}}
