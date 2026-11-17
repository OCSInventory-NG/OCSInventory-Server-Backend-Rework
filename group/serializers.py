from asset.asset_group.models import AssetGroup
from django.contrib.auth.models import Group
from group.models import GroupAssetScope, GroupProtection
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class GroupSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    is_protected = serializers.BooleanField(required=False, write_only=True)
    asset_groups = serializers.ManyRelatedField(
        child_relation=serializers.PrimaryKeyRelatedField(
            queryset=AssetGroup.objects.all()
        ),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Group
        fields = ["id", "name", "permissions", "is_protected", "asset_groups"]
        expandable_fields = {}

    def validate_asset_groups(self, asset_groups):
        if asset_groups and any(g.visibility != "public" for g in asset_groups):
            raise serializers.ValidationError(
                "Only public asset groups can be used as a scope."
            )
        return asset_groups

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        protection = getattr(instance, "protection", None)
        representation["is_protected"] = bool(protection and protection.is_protected)
        scope = getattr(instance, "asset_scope", None)
        representation["asset_groups"] = (
            None if scope is None else sorted(g.id for g in scope.asset_groups.all())
        )
        return representation

    def _apply_scope(self, group, asset_groups):
        if asset_groups is None:
            GroupAssetScope.objects.filter(group=group).delete()
        else:
            scope, _ = GroupAssetScope.objects.get_or_create(group=group)
            scope.asset_groups.set(asset_groups)
        group._state.fields_cache.pop("asset_scope", None)

    def create(self, validated_data):
        is_protected = validated_data.pop("is_protected", False)
        has_scope = "asset_groups" in validated_data
        asset_groups = validated_data.pop("asset_groups", None)
        group = super().create(validated_data)
        if has_scope:
            self._apply_scope(group, asset_groups)
        GroupProtection.objects.update_or_create(
            group=group,
            defaults={"is_protected": is_protected},
        )
        return group

    def update(self, instance, validated_data):
        is_protected = validated_data.pop("is_protected", None)
        has_scope = "asset_groups" in validated_data
        asset_groups = validated_data.pop("asset_groups", None)
        group = super().update(instance, validated_data)
        if has_scope:
            self._apply_scope(group, asset_groups)
        if is_protected is not None:
            GroupProtection.objects.update_or_create(
                group=group,
                defaults={"is_protected": is_protected},
            )
        return group
