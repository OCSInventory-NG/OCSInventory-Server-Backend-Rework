from rest_framework import serializers
from .models import AuthMethod


class AuthMethodSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthMethod
        fields = ["id", "name", "priority", "enabled"]
