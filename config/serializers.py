from config.models import Config
from rest_framework import serializers


class ConfigSerializer(serializers.ModelSerializer):
    """
    [summary]

    Args:
        serializers ([type]): [description]
    """

    class Meta:
        model = Config
        fields = ['name', 'value']
        # list_serializer_class = UpdateConfigSerializer



