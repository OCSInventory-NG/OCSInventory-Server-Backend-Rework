from snmp.snmp_config.models import SnmpConfig
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class SnmpConfigSerializer(ExpandableSerializer):
    """
    This serializer class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = SnmpConfig
        fields = [
            "id",
            "name",
            "version",
            "user",
            "auth_level",
            "password",
            "auth_protocol",
            "priv_protocol",
            "priv_password",
            "retries",
            "timeout",
            "subnets",
        ]

        expandable_fields = {
            "subnets": "snmp.subnet.serializers.SubnetSerializer",
        }
