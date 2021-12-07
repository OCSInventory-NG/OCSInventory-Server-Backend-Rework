from accountinfo.models import AccountinfoValue, AccountinfoData, AccountinfoConfig
from rest_framework import serializers
from asset.base.models import Base

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

class AccountinfoGenericRelation(serializers.RelatedField):

    def to_representation(self, value):

        if isinstance(value, Base):
            return value.id
        raise Exception('Unexpected type of tagged object')

class AccountinfoDataSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    generic_data = AccountinfoGenericRelation(source='content_object', read_only=True)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoData
        fields = [
            'id',
            'accountdata',
            'generic_data'
        ]


