from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([HyperlinkedModelSerializer])
    """
    class Meta:
        """
        Define the linked model and the fields registered in the API
        """
        model = User
        fields = ['url', 'username', 'email', 'is_staff']
