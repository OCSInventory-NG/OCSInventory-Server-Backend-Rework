from django.contrib.auth.models import Group
from group.models import GroupProtection
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class GroupSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    is_protected = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Group
        fields = ["id", "name", "permissions", "is_protected"]
        expandable_fields = {}

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        protection = getattr(instance, "protection", None)
        representation["is_protected"] = bool(protection and protection.is_protected)
        return representation

    def create(self, validated_data):
        is_protected = validated_data.pop("is_protected", False)
        group = super().create(validated_data)
        GroupProtection.objects.update_or_create(
            group=group,
            defaults={"is_protected": is_protected},
        )
        return group

    def update(self, instance, validated_data):
        is_protected = validated_data.pop("is_protected", None)
        group = super().update(instance, validated_data)
        if is_protected is not None:
            GroupProtection.objects.update_or_create(
                group=group,
                defaults={"is_protected": is_protected},
            )
        return group
