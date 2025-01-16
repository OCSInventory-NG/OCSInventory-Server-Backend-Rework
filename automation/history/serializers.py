from automation.history.models import History
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class HistorySerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = History
        fields = ["id", "scheduler", "date", "status", "comment"]
