from rest_framework import serializers
from snmp.scanner.models import SnmpScanner
from snmp.snmp_config.models import SnmpConfig
from snmp.snmp_config.serializers import SnmpConfigSerializer


class SnmpScannerSerializer(serializers.ModelSerializer):
    """
    This serializer class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    configs = serializers.PrimaryKeyRelatedField(
        queryset=SnmpConfig.objects.all(), many=True
    )

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = SnmpScanner
        fields = [
            "identifier",
            "ip",
            "subnets",
            "notes",
            "last_updated",
            "total_scanned",
            "total_found",
            "last_scan_date",
            "configs",
        ]
        extra_kwargs = {"last_updated": {"read_only": True}}

    def to_representation(self, instance):
        """
        Custom method to use SnmpConfigSerializer for representing configs
        """
        representation = super().to_representation(instance)
        representation["configs"] = SnmpConfigSerializer(
            instance.configs.all(), many=True
        ).data
        return representation
