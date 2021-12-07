from accountinfo.models import AccountinfoValue, AccountinfoData, AccountinfoConfig
from rest_framework import serializers


class AccountinfoConfigSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoConfig
        fields = [
            'id',
            'name',
            'description',
            'datatype',
            'datatarget'
        ]

class AccountinfoValueSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoValue
        fields = [
            'id',
            'accountinfo_config',
            'value'
        ]

class AccountinfoDataSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoData
        fields = [
            'id',
            'accountdata'
        ]
