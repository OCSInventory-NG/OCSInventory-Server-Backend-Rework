from asset.inventory_section.models import InventorySection
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer
from asset.inventory_field.serializers import InventoryFieldSerializer


class InventorySectionSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    Serializer class for InventorySection
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventorySection
        fields = [
            "id",
            "base",
            "template_section",
            "fields",
        ]

        expandable_fields = {
            "fields": InventoryFieldSerializer,
        }
