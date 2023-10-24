from rest_framework import serializers
from .models import AuthMapping


class AuthMappingSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthMapping
        fields = ["id", "auth_config", "external_field", "internal_field"]
