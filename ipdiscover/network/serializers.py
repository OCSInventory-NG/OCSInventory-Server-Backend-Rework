from ipdiscover.network.models import Network
from rest_framework import serializers


class NetworkSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Network
        fields = [
            'id',
            'name',
            'description',
            'netid',
            'mask',
            'group'
        ]

