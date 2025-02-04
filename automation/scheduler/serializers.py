from automation.scheduler.models import Scheduler
from rest_framework import serializers


class SchedulerSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Scheduler
        fields = [
            "id",
            "name",
            "description",
            "active",
            "recurrence",
            "last_execution",
            "hour",
            "day_of_week",
            "day_of_month",
        ]
