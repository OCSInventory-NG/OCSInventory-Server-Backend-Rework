from snmp.scanner.models import SnmpScanner
from rest_framework import serializers
from snmp.snmp_config.serializers import SnmpConfigSerializer


class SnmpScannerSerializer(serializers.ModelSerializer):
    """
    This serializer class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    configs = SnmpConfigSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = SnmpScanner
        fields = ["identifier", "ip", "subnets", "notes", "last_updated", "total_scanned", "total_found", "last_scan_date", "configs"]
        extra_kwargs = {
                        "last_updated": {"read_only": True}
                        }
