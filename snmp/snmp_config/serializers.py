from rest_framework import serializers
from snmp.snmp_config.models import SnmpConfig


class SnmpConfigSerializer(serializers.ModelSerializer):
    """
    This serializer class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = SnmpConfig
        fields = ["id", "name", "version", "user", "auth_level", "password",
                  "auth_protocol", "priv_protocol", "priv_password", "retries",
                  "timeout", "subnets"]
