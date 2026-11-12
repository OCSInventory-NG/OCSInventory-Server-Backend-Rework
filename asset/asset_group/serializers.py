from asset.inventory_base.serializers import InventoryBaseSerializer
from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer, ValidationError
from user.serializers import UserSerializer

from .models import AssetGroup


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
