from permission.permissions import DefaultModelPermissions
from inventory.template.models import Template
from inventory.template.serializers import TemplateSerializer
from ocsinventory_backend.ocs_framework import viewsets


class TemplateViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    model = Template
