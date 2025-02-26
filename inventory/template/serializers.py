from inventory.template.models import Template
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class TemplateSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """
    
    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Template
        fields = ["id", "name", "os", "last_update", "sections"]

        expandable_fields = {
            "sections": {
                "serializer": "inventory.section.serializers.SectionSerializer",
                "many": True,
                "required": False
            }
        }
        extra_kwargs = {"last_update": {"read_only": True}}

    def create(self, validated_data):
        """Override create to allow nested creation of sections"""
        if "sections" in validated_data.keys():
            # If sections are present
            sections = validated_data.pop("sections")
            parent = super().create(validated_data)

            for section in sections:
                section["template"] = parent
            self.fields["sections"].create(sections)
        else:
            parent = super().create(validated_data)

        return parent
