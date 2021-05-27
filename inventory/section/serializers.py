from inventory.section.models import Section
from rest_framework import serializers


class SectionSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Section
        fields = ['id', 'name', 'retrival_method', 'target', 'template']
