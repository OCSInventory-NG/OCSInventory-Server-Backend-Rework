from automation.history.models import History
from rest_framework import serializers


class HistorySerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = History
        fields = ["id", "scheduler", "date", "status", "comment"]
