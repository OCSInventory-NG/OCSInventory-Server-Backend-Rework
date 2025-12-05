from inventory.software.models import SoftwareFieldMapping
from inventory.software.serializers import SoftwareFieldMappingSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class SoftwareFieldMappingViewSet(viewsets.OCSViewSet):
    permission_classes = [DefaultModelPermissions]

    queryset = SoftwareFieldMapping.objects.all()
    serializer_class = SoftwareFieldMappingSerializer
    model = SoftwareFieldMapping

    filterset_fields = ["id", "template", "template_section", "template_field", "field_key",]
