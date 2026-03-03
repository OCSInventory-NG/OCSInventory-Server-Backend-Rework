from django.contrib.auth.models import User
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class UserSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_superuser",
            "groups",
            "user_permissions",
        ]
        extra_kwargs = {"password": {"write_only": True}}
        expandable_fields = {}

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
            email=validated_data["email"],
            username=validated_data["username"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            is_superuser=validated_data["is_superuser"],
        )

        user.set_password(validated_data["password"])
        user.save()

        if validated_data.get("groups") is not None:
            user.groups.set(validated_data["groups"])
        if validated_data.get("user_permissions") is not None:
            user.user_permissions.set(validated_data["user_permissions"])

        user.save()

        return user

    def update(self, instance, validated_data):
        """Override update method to manage password setting

        Args:
            instance ([User]): User object currently edited
            validated_data ([Array]): Data provided to the API

        Returns:
            [User]: Updated user
        """
        instance = super().update(instance, validated_data)

        if validated_data.get("groups") is not None:
            instance.groups.set(validated_data["groups"])
        if validated_data.get("user_permissions") is not None:
            instance.user_permissions.set(validated_data["user_permissions"])
        if validated_data.get("password") is not None:
            instance.set_password(validated_data["password"])
        instance.save()

        return instance


class MyAccountSerializer(UserSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_staff",
            "groups",
            "user_permissions",
        ]
        extra_kwargs = {"password": {"write_only": True}}
