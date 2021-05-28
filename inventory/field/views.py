from permission.permissions import DefaultModelPermissions
from inventory.field.models import Field
from inventory.field.serializers import FieldSerializer
from ocsinventory_backend.ocs_framework import viewsets


class FieldViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Field.objects.all()
    serializer_class = FieldSerializer
    model = Field
