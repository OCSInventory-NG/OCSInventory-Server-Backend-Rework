from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = User
        fields = ['id', 'username', 'email', 'first_name',
                  'last_name',  'password', 'is_staff',
                  'groups', 'user_permissions']
        extra_kwargs = {'password': {'write_only': True}}

    @staticmethod
    def create(validated_data):
        """
        Override existing create method to ensure password is encrypted

        Args:
            validated_data : POST request

        Returns:
            [user]
        """
        user = User(
            email=validated_data['email'],
            username=validated_data['username'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            is_staff=validated_data['is_staff'],
            user_permissions=validated_data['user_permissions'],
            groups=validated_data['groups'],
        )
        user.set_password(validated_data['password'])
        user.save()

        return user

class MyAccountSerializer(UserSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = User
        fields = ['id', 'username', 'email', 'first_name',
                  'last_name',  'password', 'is_staff',
                  'groups', 'user_permissions']
        extra_kwargs = {'password': {'write_only': True}}