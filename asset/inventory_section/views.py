from asset.inventory_section.models import InventorySection
from asset.inventory_section.serializers import InventorySectionSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class InventorySectionViewSet(viewsets.OCSViewSet):
    """
    Inventory Section ViewSet

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = InventorySection.objects.all()
    serializer_class = InventorySectionSerializer
    model = InventorySection

    filterset_fields = ["id", "base", "template_section"]
