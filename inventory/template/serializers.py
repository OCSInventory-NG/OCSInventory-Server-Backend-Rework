from inventory.template.models import Template
from inventory.section.serializers import SectionSerializer
from rest_framework import serializers


class TemplateSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Template
        fields = ['id', 'name', 'os', 'last_update', 'sections']
        extra_kwargs = {'last_update': {'read_only': True}}
