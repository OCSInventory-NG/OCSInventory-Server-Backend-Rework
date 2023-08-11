from inventory.section.models import Section
from inventory.section.serializers import SectionSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class SectionViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    model = Section

    filterset_fields = ['id', 'name', 'target', 'retrival_method', 'retrival_output', 'template' ]

