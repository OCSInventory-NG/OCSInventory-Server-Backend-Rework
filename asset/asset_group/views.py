from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions

from .models import AssetGroup
from .serializers import AssetGroupSerializer


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
