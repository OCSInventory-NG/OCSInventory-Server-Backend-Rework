from asset.base.models import Base
from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Base
        fields = [
            'id',
            'name',
            'description',
            'serial',
            'osname',
            'osversion',
            'uuid',
            'srcip',
            'srcmac',
            'domain',
            'last_update'
        ]
        extra_kwargs = {'last_update': {'read_only': True}}
