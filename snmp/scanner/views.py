from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from snmp.scanner.serializers import SnmpScannerSerializer
from snmp.scanner.models import SnmpScanner


class SnmpScannerViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    # Set default filter
    filter_backends = []

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = SnmpScanner.objects.all()
    serializer_class = SnmpScannerSerializer
    model = SnmpScanner
