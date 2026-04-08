from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import (
    CharField,
    IntegerField,
    ModelSerializer,
    Serializer,
    SerializerMethodField,
)
from user.models import UserGroupAssignment
from user.services import sync_source_groups


class UserGroupAssignmentSerializer(Serializer):
    group_id = IntegerField(required=True)
    group_name = CharField(read_only=True)
    source = CharField(required=True)
    source_model = CharField(required=False, allow_null=True, allow_blank=True)
    source_object_id = IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        group_id = attrs["group_id"]
        source = attrs["source"]
        source_model = attrs.get("source_model")
        source_object_id = attrs.get("source_object_id")
        valid_sources = {choice[0] for choice in UserGroupAssignment.SOURCE_CHOICES}

        if source_model == "":
            source_model = None
            attrs["source_model"] = None

        if not Group.objects.filter(id=group_id).exists():
            raise serializers.ValidationError({"group_id": "Unknown group"})

        if source not in valid_sources:
            raise serializers.ValidationError({"source": "Invalid source"})

        if source == "manual":
            if source_model is not None or source_object_id is not None:
                raise serializers.ValidationError(
                    "manual source must not define source_model/source_object_id"
                )
            attrs["source_content_type"] = None
            return attrs

        if source_model is None or source_object_id is None:
            raise serializers.ValidationError(
                "source_model and source_object_id are required for non-manual sources"
            )

        if "." not in source_model:
            raise serializers.ValidationError(
                {"source_model": "Expected '<app_label>.<model>' format"}
            )

        app_label, model = source_model.split(".", 1)
        try:
            source_content_type = ContentType.objects.get_by_natural_key(
                app_label=app_label,
                model=model,
            )
        except ContentType.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"source_model": "Unknown source model"}
            ) from exc

        model_class = source_content_type.model_class()
        if model_class is None or not model_class.objects.filter(
            pk=source_object_id
        ).exists():
            raise serializers.ValidationError(
                {"source_object_id": "Unknown source object"}
            )

        attrs["source_content_type"] = source_content_type
        return attrs

    @staticmethod
    def _render_source_model(instance):
        if instance.source_content_type_id is None:
            return None
        return (
            f"{instance.source_content_type.app_label}."
            f"{instance.source_content_type.model}"
        )

    def to_representation(self, instance):
        """stable response shape for group assignment"""
        return {
            "group_id": instance.group_id,
            "group_name": instance.group.name,
            "source": instance.source,
            "source_model": self._render_source_model(instance),
            "source_object_id": instance.source_object_id,
        }


class UserSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    group_assignments = SerializerMethodField(read_only=True)

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
            "group_assignments",
            "user_permissions",
        ]
        extra_kwargs = {"password": {"write_only": True}}
        expandable_fields = {}

    @staticmethod
    def build_group_assignments_payload(user):
        """Serialize per source group assignment details for a user"""
        cached_assignments = getattr(user, "_prefetched_objects_cache", {}).get(
            "usergroupassignment_set"
        )
        if cached_assignments is None:
            assignments = (
                UserGroupAssignment.objects.filter(user=user)
                .select_related("group", "source_content_type")
                .order_by("group__name", "source")
            )
        else:
            assignments = sorted(
                cached_assignments,
                key=lambda assignment: (
                    assignment.group.name.lower(),
                    assignment.source,
                    assignment.group_id,
                ),
            )

        return UserGroupAssignmentSerializer(assignments, many=True).data

    def get_group_assignments(self, instance):
        """Expose read only assignment provenance in User api"""
        return self.build_group_assignments_payload(instance)

    @staticmethod
    def create(validated_data):
        """
        Override existing create method to ensure password is encrypted

        Args:
            validated_data : POST request

        Returns:
            [user]
        """
        groups = validated_data.pop("groups", None)
        user_permissions = validated_data.pop("user_permissions", None)

        user = User(
            email=validated_data["email"],
            username=validated_data["username"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            is_superuser=validated_data["is_superuser"],
        )

        user.set_password(validated_data["password"])
        user.save()

        if groups is not None:
            sync_source_groups(user, "manual", groups)
        if user_permissions is not None:
            user.user_permissions.set(user_permissions)

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
        groups = validated_data.pop("groups", None)
        user_permissions = validated_data.pop("user_permissions", None)

        instance = super().update(instance, validated_data)

        if groups is not None:
            sync_source_groups(
                instance,
                "manual",
                groups,
            )
        if user_permissions is not None:
            instance.user_permissions.set(user_permissions)
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
            "is_superuser",
            "groups",
            "group_assignments",
            "user_permissions",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "is_superuser": {"read_only": True},
            "groups": {"read_only": True},
            "group_assignments": {"read_only": True},
            "user_permissions": {"read_only": True},
        }
