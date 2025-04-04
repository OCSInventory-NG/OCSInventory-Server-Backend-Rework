from inventory.category.models import Category
from inventory.section.serializers import SectionSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class CategorySerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Category
        fields = ["id", "name", "description", "inventory_sections", "is_protected"]
        expandable_fields = {"inventory_sections": SectionSerializer}
