from snmp.scanner.models import SnmpScanner
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer

class SnmpScannerSerializer(ExpandableSerializer):
    """
    This serializer class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

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
            "assets",
        ]
        extra_kwargs = {"last_updated": {"read_only": True}}

        expandable_fields = {
            "configs": "snmp.snmp_config.serializers.SnmpConfigSerializer",
            "assets": "asset.inventory_base.serializers.InventoryBaseSerializer",
        }