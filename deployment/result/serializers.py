from asset.asset_group.models import AssetGroup
from asset.asset_group.serializers import AssetGroupSerializer
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.scope import visible_asset_ids_for
from asset.inventory_base.serializers import InventoryBaseSerializer
from deployment.result.models import Result
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer


class ResultSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serializer class provides the API representation
    """

    # using primary key related field to avoid circular import
    asset = serializers.PrimaryKeyRelatedField(
        queryset=InventoryBase.objects.all(),
        allow_null=True,
        error_messages={"does_not_exist": "Unknown asset."},
    )
    group = serializers.PrimaryKeyRelatedField(
        queryset=AssetGroup.objects.all(), allow_null=True
    )

    class Meta:
        model = Result
        fields = [
            "id",
            "package",
            "asset",
            "group",
            "name",
            "status",
            "comment",
            "date_created",
        ]

        expandable_fields = {
            "asset": InventoryBaseSerializer,
            "group": AssetGroupSerializer,
        }
        extra_kwargs = {"package": {"required": False}}

    def _scope_ids(self):
        return visible_asset_ids_for(self.context.get("request"))

    def get_fields(self):
        fields = super().get_fields()
        ids = self._scope_ids()
        if ids is not None:
            fields["asset"].queryset = InventoryBase.objects.filter(pk__in=ids)
        return fields

    def validate_group(self, group):
        ids = self._scope_ids()
        if ids is None or group is None:
            return group
        # shared by every row of a list POST, which repeats the same group
        outside = self.context.setdefault("_group_outside_scope", {})
        if group.pk not in outside:
            outside[group.pk] = group.assets.exclude(pk__in=ids).exists()
        if outside[group.pk]:
            raise serializers.ValidationError(
                "Asset group contains assets outside your scope."
            )
        return group
