from snmp.scanner.models import SnmpScanner
from rest_framework import serializers


class SnmpScannerSerializer(serializers.ModelSerializer):
    """
    This serializer class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = SnmpScanner
        fields = ["name", "ip", "subnets"]

