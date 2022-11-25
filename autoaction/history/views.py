from autoaction.history.models import History
from autoaction.history.serializers import HistorySerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions

# Create your views here.
class HistoryViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    permission_classes = [DefaultModelPermissions]

    queryset = History.objects.all()
    serializer_class = HistorySerializer
    model = History