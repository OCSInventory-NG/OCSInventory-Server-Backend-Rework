from ipdiscover.network.models import Network
from ipdiscover.netgroup.serializers import NetgroupSerializer
from ipdiscover.netdevice.serializers import NetdeviceSerializer
from rest_framework import serializers


class NetworkSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    netdevices = NetdeviceSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Network
        fields = [
            'id',
            'name',
            'description',
            'netid',
            'mask',
            'netdevices',
            'group'
        ]
        extra_kwargs = {
            "name": {"required": False},
            "description":  {"required": False},
            "location": {'required': False}
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        if 'netdevices' in validated_data.keys():
            # If netdevices are present
            netdevices = validated_data.pop('netdevices')
            parent = super().create(validated_data)

            for netdevice in netdevices:
                netdevice['network'] = parent
            self.fields['netdevices'].create(netdevices)
        else:
            parent = super().create(validated_data)

        return parent
