from deployment.result.models import Result
from deployment.result.serializers import ResultSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class ResultViewSet(viewsets.OCSViewSet):
    """
    View behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Result.objects.all()
    serializer_class = ResultSerializer
    model = Result
