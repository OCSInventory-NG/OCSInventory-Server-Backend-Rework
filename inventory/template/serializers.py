from inventory.template.models import Template
from inventory.section.serializers import SectionSerializer
from rest_framework import serializers


class TemplateSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    sections = SectionSerializer(many=True)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Template
        fields = ['id', 'name', 'os', 'last_update', 'sections']
        extra_kwargs = {'last_update': {'read_only': True}}

    def create(self, validated_data):
        """Override create to allow nested creation of sections"""

        # If sections are present
        sections = validated_data.pop('sections')
        parent = super().create(validated_data)

        for section in sections:
            section['template'] = parent
        self.fields['sections'].create(sections)

        return parent
