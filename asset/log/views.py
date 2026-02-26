from asset.log.models import Log
from asset.log.serializers import LogSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class LogViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Log.objects.all()
    serializer_class = LogSerializer
    model = Log
    search_fields = ["asset__name", "scope", "comment"]
    ordering_fields = ["id", "asset", "timestamp", "scope", "comment"]
