from config.models import Config
from rest_framework import serializers


class ConfigSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Config
        fields = ['name', 'value']
