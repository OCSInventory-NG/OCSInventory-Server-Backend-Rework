from accountinfo.models import AccountinfoValue, AccountinfoData, AccountinfoConfig
from rest_framework import serializers
from asset.base.models import Base
from django.contrib.contenttypes.models import ContentType


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
            'accountdata',
            'object_slug',
            'object_id'
        ]

    def create(self, validated_data):
        """Override create to allow nested creation of fields"""
        content_type = validated_data.get('object_slug')
        app, model = content_type.split(".")
        ct = ContentType.objects.get_by_natural_key(
            app_label=app,
            model=model
        )

        object_id = validated_data.get('object_id')

        self.save(
            accountdata=validated_data.get('accountdata'),
            content_type=ct,
            object_id=object_id
        )


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


class AccountinfoConfigSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    accountinfo_values = AccountinfoValueSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AccountinfoConfig
        fields = [
            'id',
            'name',
            'description',
            'datatype',
            'datatarget',
            'accountinfo_values'
        ]
        extra_kwargs = {'accountinfo_values': {'read_only': True}}
