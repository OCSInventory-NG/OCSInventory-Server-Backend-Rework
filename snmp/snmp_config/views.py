from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from snmp.snmp_config.models import SnmpConfig
from snmp.snmp_config.serializers import SnmpConfigSerializer


class SnmpConfigViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSViewSet])
    """

    # Set default filter
    filter_backends = []

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = SnmpConfig.objects.all()
    serializer_class = SnmpConfigSerializer
    model = SnmpConfig
