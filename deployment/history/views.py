from deployment.history.models import DeploymentHistory
from deployment.history.serializers import DeploymentHistorySerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class DeploymentHistoryViewSet(viewsets.OCSViewSet):
    """
    View behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = DeploymentHistory.objects.all()
    serializer_class = DeploymentHistorySerializer
    model = DeploymentHistory
