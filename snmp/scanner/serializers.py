from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer
from snmp.scanner.models import SnmpScanner
from snmp.snmp_config.serializers import SnmpConfigSerializer
from asset.inventory_base.serializers import InventoryBaseSerializer


class SnmpScannerSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serializer class provide the API representation
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
            "configs": SnmpConfigSerializer,
            "assets": InventoryBaseSerializer,
        }
