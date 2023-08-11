from deployment.history.models import History
from deployment.history.serializers import HistorySerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class HistoryViewSet(viewsets.OCSViewSet):
    """
    View behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = History.objects.all()
    serializer_class = HistorySerializer
    model = History
