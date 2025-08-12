from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import filters
from snmp.scanner.models import SnmpScanner
from snmp.scanner.serializers import SnmpScannerSerializer


class SnmpScannerViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    # Set default filter
    filter_backends = [filters.OrderingFilter]

    ordering = ["identifier"]

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = SnmpScanner.objects.all()
    serializer_class = SnmpScannerSerializer
    model = SnmpScanner
