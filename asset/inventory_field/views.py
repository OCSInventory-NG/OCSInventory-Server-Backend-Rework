from permission.permissions import DefaultModelPermissions
from ocsinventory_backend.ocs_framework import viewsets
from asset.inventory_field.models import InventoryField
from asset.inventory_field.serializers import InventoryFieldSerializer


class InventoryFieldViewSet(viewsets.OCSViewSet):
    """
    Template Field ViewSet

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = InventoryField.objects.all()
    serializer_class = InventoryFieldSerializer
    model = InventoryField

    filterset_fields = ['id', 'inventory_section', 'template_field', 'value']
