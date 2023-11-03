from rest_framework import serializers
from .models import AuthMapping


class AuthMappingSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthMapping
        fields = '__all__'

    def validate(self, data):
        # TODO: validation logic here
        # Check if the same EXTERNAL or INTERNAL FIELD is already set
        return data

    def create(self, validated_data):
        # TODO: create logic here
        return AuthMapping.objects.create(**validated_data)
