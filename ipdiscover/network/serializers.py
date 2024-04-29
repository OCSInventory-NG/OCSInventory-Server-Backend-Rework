from ipdiscover.netdevice.serializers import NetdeviceSerializer
from ipdiscover.network.models import Network
from ipdiscover.netdevice.models import Netdevice
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
            "id",
            "nettag",
            "name",
            "description",
            "netid",
            "mask",
            "netdevices",
            "group",
            "last_update"
        ]
        extra_kwargs = {
            "name": {"required": False},
            "description": {"required": False},
            "location": {"required": False},
            "last_update": {"read_only": True},
        }

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        if "nettag" not in validated_data.keys():
            validated_data["nettag"] = validated_data["netid"]

        if "netdevices" in validated_data.keys():
            # If netdevices are present
            netdevices = validated_data.pop("netdevices")
            parent = super().create(validated_data)

            for netdevice in netdevices:
                netdevice["network"] = parent
            self.fields["netdevices"].create(netdevices)
        else:
            parent = super().create(validated_data)

        return parent

    def update(self, instance, validated_data):
        """Override update to allow nested updates"""
        # if value not specified, current data should not be updated
        # w/ default or blank but left as is (name and description especiallly)
        instance.nettag = validated_data.get('nettag', instance.nettag)
        # name not provided, do not update if current name != default value (netid)
        update_name = validated_data.get('name', instance.name)
        instance.name = update_name if update_name != instance.netid else instance.name
        # same goes for description (default = "default description")
        update_description = validated_data.get('description', instance.description)
        instance.description = (update_description if update_description
                                != "default description" else instance.description)
        instance.netid = validated_data.get('netid', instance.netid)
        instance.mask = validated_data.get('mask', instance.mask)
        instance.group = validated_data.get('group', instance.group)
        instance.save()

        # get all existing netdevices in database for this network
        set_netdevice = list(Netdevice.objects.filter(network=instance).values('ip'))
        set_netdevice = [device['ip'] for device in set_netdevice]

        if "netdevices" in validated_data.keys():
            netdevices = validated_data.pop('netdevices')
            for device in netdevices:
                try:
                    netdevice = Netdevice.objects.get(ip=device['ip'], network=instance)
                    netdevice.netname = device.get('netname', netdevice.netname)
                    netdevice.mac = device.get('mac', netdevice.mac)
                    netdevice.save()
                except Netdevice.DoesNotExist:
                    device['network'] = instance
                    netdevice = Netdevice.objects.create(**device)

        return instance
