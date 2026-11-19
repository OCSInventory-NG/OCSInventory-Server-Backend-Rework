from asset.inventory_base.scope import AssetScopeMixin
from asset.inventory_field.models import InventoryField
from asset.inventory_field.serializers import InventoryFieldSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class InventoryFieldViewSet(AssetScopeMixin, viewsets.OCSViewSet):
    """
    Template Field ViewSet

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]
    asset_scope_field = "inventory_section__base"

    queryset = InventoryField.objects.all()
    serializer_class = InventoryFieldSerializer
    model = InventoryField

    filterset_fields = ["id", "inventory_section", "template_field", "value"]
