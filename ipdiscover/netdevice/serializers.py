from ipdiscover.netdevice.models import Netdevice
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class NetdeviceSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Netdevice
        fields = ["id", "ip", "netname", "mac", "network", "last_seen"]
        extra_kwargs = {
            "network": {"required": False},
            "last_seen": {"read_only": True}
        }
