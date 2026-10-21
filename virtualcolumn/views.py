from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from virtualcolumn.models import ColumnLayout, VirtualCol
from virtualcolumn.serializers import ColumnLayoutSerializer, VirtualColSerializer


class VirtualColViewSet(viewsets.RestrictVisibilityViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([RestrictVisibilityViewSet])
    """

    permission_classes = [DefaultModelPermissions]

    queryset = VirtualCol.objects.all()
    serializer_class = VirtualColSerializer
    model = VirtualCol

    filterset_fields = ["id", "name", "target"]

    def perform_create(self, serializer):
        """The creator owns the column"""
        serializer.save(user=self.request.user)


class ColumnLayoutViewSet(viewsets.RestrictVisibilityViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([RestrictVisibilityViewSet])
    """

    permission_classes = [DefaultModelPermissions]

    queryset = ColumnLayout.objects.all()
    serializer_class = ColumnLayoutSerializer
    model = ColumnLayout

    filterset_fields = ["id", "name", "target"]

    def perform_create(self, serializer):
        """The creator owns the layout"""
        serializer.save(user=self.request.user)
