from asset.inventory_field.models import InventoryField
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class InventoryFieldSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    Serializer class for InventoryField
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = InventoryField
        fields = ["id", "inventory_section", "template_field", "value"]
