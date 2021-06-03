from asset.base.models import Base
from rest_framework import serializers
from inventory.template.models import Template
from rest_framework.exceptions import APIException


class BaseSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    # OS name constant that will determine the template
    OS_WIN = "windows"
    OS_LIN = "linux"
    OS_MAC = "mac"

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
            'template',
            'last_update'
        ]
        extra_kwargs = {
            'last_update': {'read_only': True}
        }
        http_method_names = ['get', 'post', 'patch', 'delete']

    def create(self, validated_data):
        """
        Override existing create method to set the template link

        Args:
            validated_data : POST request

        Returns:
            [Base] object
        """
        assetBase = super().create(validated_data)

        osname = validated_data['osname'].lower()

        # Determine OS for template management
        try:
            if self.OS_WIN in osname:
                assetBase.template = Template.objects.filter(os="WIN")[0]
            elif self.OS_LIN in osname:
                assetBase.template = Template.objects.filter(os="LIN")[0]
            elif self.OS_MAC in osname:
                assetBase.template = Template.objects.filter(os="MAC")[0]

            assetBase.save()
        except APIException:
            print("An error happenned")

        return assetBase
