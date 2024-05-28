from frontend.dashboard.models import Dashboard
from frontend.dashboard.serializers import DashboardSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class DashboardViewSet(viewsets.OCSViewSet):
    """
    this class will permit the frontend server to manage configuration
    for the dashboard.
    """

    filter_backends = []

    permission_classes = [DefaultModelPermissions]

    queryset = Dashboard.objects.all()
    serializer_class = DashboardSerializer
    model = Dashboard
