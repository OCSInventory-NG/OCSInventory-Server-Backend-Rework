from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from snmp.scanner.serializers import SnmpScannerSerializer
from snmp.scanner.models import SnmpScanner
from snmp.snmp_config.serializers import SnmpConfigSerializer
from snmp.snmp_config.models import SnmpConfig
from rest_framework.response import Response


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

    def list(self, request, *args, **kwargs):
        scanners = SnmpScanner.objects.all()
        scanners = SnmpScannerSerializer(scanners, many=True).data
        for scanner in scanners:
            configs = SnmpConfig.objects.filter(id__in=scanner["configs"])
            scanner["configs"] = SnmpConfigSerializer(configs, many=True).data
        return Response(scanners, status=200)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        scanner = SnmpScannerSerializer(instance).data
        configs = SnmpConfig.objects.filter(id__in=scanner["configs"])
        scanner["configs"] = SnmpConfigSerializer(configs, many=True).data
        return Response(scanner, status=200)
