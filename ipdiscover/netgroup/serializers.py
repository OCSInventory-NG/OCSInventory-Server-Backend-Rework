from ipdiscover.netgroup.models import Netgroup
from rest_framework import serializers


class NetgroupSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Netgroup
        fields = [
            'id',
            'name',
            'description'
        ]
