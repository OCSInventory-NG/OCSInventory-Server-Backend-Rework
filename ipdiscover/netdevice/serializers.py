from ipdiscover.netdevice.models import Netdevice
from rest_framework import serializers


class NetdeviceSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Netdevice
        fields = [
            'id',
            'ip',
            'netname',
            'mac',
            'network'
        ]

