from asset.inventory_base.models import InventoryBase
from asset.inventory_base.serializers import InventoryBaseSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class InventoryBaseViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = InventoryBase.objects.all()
    serializer_class = InventoryBaseSerializer
    model = InventoryBase
    search_fields = [
        "name",
        "description",
        "serial",
        "osname",
        "osversion",
        "uuid",
        "srcip",
        "srcmac",
        "domain",
        "agent",
        "last_update",
    ]
    ordering_fields = [
        "id",
        "name",
        "description",
        "serial",
        "osname",
        "osversion",
        "uuid",
        "srcip",
        "srcmac",
        "domain",
        "agent",
        "last_update",
    ]
