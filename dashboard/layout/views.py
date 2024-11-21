from dashboard.layout.models import DashboardLayout
from dashboard.layout.serializers import DashboardLayoutSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class DashboardLayoutViewSet(viewsets.OCSViewSet):
    """
    this class will permit the frontend server to manage configuration
    for the dashboard.
    """

    filter_backends = []

    permission_classes = [DefaultModelPermissions]

    queryset = DashboardLayout.objects.all()
    serializer_class = DashboardLayoutSerializer
    model = DashboardLayout
