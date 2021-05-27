from inventory.template.models import Template
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Template
        fields = ['id', 'name', 'os', 'last_update']
        extra_kwargs = {'last_update': {'read_only': True}}
