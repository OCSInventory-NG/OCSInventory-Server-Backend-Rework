from asset.base.models import Base
from asset.base.serializers import BaseSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class BaseViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Base.objects.all()
    serializer_class = BaseSerializer
    model = Base
