from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.exceptions import APIException

from .models import AssetGroup
from .serializers import AssetGroupSerializer


class AssetGroupInScope(APIException):
    status_code = 409
    default_detail = "This asset group is used as a user group scope."
    default_code = "asset_group_in_scope"


class AssetGroupViewSet(viewsets.RestrictVisibilityViewSet):
    """
    AssetGroup ViewSet

    Inherits from RestrictVisibilityViewSet to restrict the visibility of the
    Search objects based on user and group membership
    """

    permission_classes = [DefaultModelPermissions]

    queryset = AssetGroup.objects.all()
    serializer_class = AssetGroupSerializer
    model = AssetGroup

    filterset_fields = ["name", "description", "is_dynamic", "assets", "last_updated"]

    def check_destroy_allowed(self, instance):
        super().check_destroy_allowed(instance)
        if instance.scoped_user_groups.exists():
            raise AssetGroupInScope()
