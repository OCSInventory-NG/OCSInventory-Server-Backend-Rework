from automation.scheduler.models import Scheduler
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class SchedulerSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
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
