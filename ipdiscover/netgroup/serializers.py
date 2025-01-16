from ipdiscover.netgroup.models import Netgroup
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class NetgroupSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Netgroup
        fields = ["id", "name", "description"]
