from django.contrib.auth.models import Permission
from rest_framework import serializers


class PermissionSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Permission
        fields = ["id", "name", "content_type", "codename"]
