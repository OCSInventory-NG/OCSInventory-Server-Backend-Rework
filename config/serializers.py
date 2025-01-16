from config.models import Config
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class ConfigSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Config
        fields = ["name", "value"]
