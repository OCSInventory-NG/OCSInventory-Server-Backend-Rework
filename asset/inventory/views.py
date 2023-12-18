from permission.permissions import DefaultModelPermissions
from ocsinventory_backend.ocs_framework import viewsets
from asset.inventory.models import InventorySection, InventoryField
from asset.inventory.serializers import InventorySectionSerializer, InventoryFieldSerializer



class InventorySectionViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = InventorySection.objects.all()
    serializer_class = InventorySectionSerializer
    model = InventorySection

    filterset_fields = ['id', 'base', 'template_section']

class InventoryFieldViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = InventoryField.objects.all()
    serializer_class = InventoryFieldSerializer
    model = InventoryField

    filterset_fields = ['id', 'inventory_section', 'template_field', 'value']
