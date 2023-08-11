from asset.inventory.models import Inventory
from asset.inventory.serializers import InventorySerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions

# Create your views here.
class InventoryViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Inventory.objects.all()
    serializer_class = InventorySerializer
    model = Inventory

    filterset_fields = ['id', 'assetId', 'sectionId', 'sectionName' ]
