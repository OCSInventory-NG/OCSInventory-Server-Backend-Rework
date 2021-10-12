from inventory.section.models import Section
from inventory.field.serializers import FieldSerializer
from rest_framework import serializers


class SectionSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    fields = FieldSerializer(many=True)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Section
        fields = [
            'id',
            'name',
            'retrival_method',
            'retrival_output',
            'target',
            'template',
            'fields'
        ]

    def create(self, validated_data):

        # If sections are present
        fields = validated_data.pop('fields')
        parent = super().create(validated_data)

        for field in fields:
            field['section'] = parent
        self.fields['fields'].create(fields)

        return parent
