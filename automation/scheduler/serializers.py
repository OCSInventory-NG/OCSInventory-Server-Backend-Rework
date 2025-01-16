from automation.scheduler.models import Scheduler
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class SchedulerSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Scheduler
        fields = ["id", "name", "description", "active", "recurence", "last_execution"]
