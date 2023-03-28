from automation.scheduler.models import Scheduler
from rest_framework import serializers


class TasksSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Scheduler
        fields = ["id", "name", "status", "task", "recurence"]
