from asset.inventory_base.models import InventoryBase
from asset.inventory_base.scope import visible_asset_ids_for
from asset.inventory_base.serializers import InventoryBaseSerializer
from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer, ValidationError
from user.serializers import UserSerializer

from .models import AssetGroup

_VISIBLE_SET_ATTR = "_visible_asset_id_set"


class AssetGroupSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    Serializer class for AssetGroup
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AssetGroup
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
        expandable_fields = {
            "user": UserSerializer,
            "groups": GroupSerializer,
            "assets": InventoryBaseSerializer,
        }

    def validate(self, attrs):
        """
        No security criterion in a dynamic group a security exclusion
        targets: the machines it leaves out would leave the group, then be
        excluded no more, and so on.
        """
        from search.security_criteria import uses_security

        instance = self.instance
        dynamic = attrs.get("is_dynamic", getattr(instance, "is_dynamic", False))
        search = attrs.get("search", getattr(instance, "search", None))
        if (
            instance is not None
            and dynamic
            and uses_security(search)
            and instance.security_exclusions.exists()
        ):
            raise ValidationError(
                {"search": "Security criteria in a group a security exclusion targets"}
            )
        return attrs

    def _scope_ids(self):
        return visible_asset_ids_for(self.context.get("request"))

    def validate_visibility(self, value):
        instance = self.instance
        if (
            instance is not None
            and value != "public"
            and instance.visibility == "public"
            and instance.scoped_user_groups.exists()
        ):
            raise ValidationError(
                "This asset group is used as a user group scope and must stay public."
            )
        return value

    def get_fields(self):
        fields = super().get_fields()
        child = fields["assets"].child_relation
        child.error_messages["does_not_exist"] = "Unknown asset."
        ids = self._scope_ids()
        if ids is not None:
            child.queryset = InventoryBase.objects.filter(pk__in=ids)
        return fields

    def _visible_id_set(self, ids):
        request = self.context["request"]
        if not hasattr(request, _VISIBLE_SET_ATTR):
            setattr(request, _VISIBLE_SET_ATTR, {pk["pk"] for pk in ids})
        return getattr(request, _VISIBLE_SET_ATTR)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        ids = self._scope_ids()
        if ids is not None:
            visible = self._visible_id_set(ids)
            representation["assets"] = [
                asset
                for asset in representation["assets"]
                if (asset["id"] if isinstance(asset, dict) else asset) in visible
            ]
        return representation

    def update(self, instance, validated_data):
        ids = self._scope_ids()
        if ids is not None and "assets" in validated_data:
            hidden = instance.assets.exclude(pk__in=ids)
            validated_data["assets"] = [*validated_data["assets"], *hidden]
        return super().update(instance, validated_data)
