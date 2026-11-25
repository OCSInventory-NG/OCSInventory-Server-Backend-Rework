from asset.inventory_base.scope import AssetScopeMixin
from deployment.result.models import Result
from deployment.result.serializers import ResultSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class ResultViewSet(AssetScopeMixin, viewsets.OCSViewSet):
    """
    View behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]
    asset_scope_field = "asset"

    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    model = Result
