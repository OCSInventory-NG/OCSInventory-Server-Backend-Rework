from rest_framework import serializers
from .models import AuthConfig


class AuthConfigSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthConfig
        fields = ["id", "auth_method", "config", "priority", "enabled"]
