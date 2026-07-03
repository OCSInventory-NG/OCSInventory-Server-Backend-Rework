from inventory.section.models import Section
from inventory.section.serializers import SectionSerializer
from inventory.template.views import TemplateVersionSnapshotMixin
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class SectionViewSet(TemplateVersionSnapshotMixin, viewsets.OCSViewSet):
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

    def get_versioned_template(self, instance):
        return instance.template

    def get_versioned_template_for_create(self, serializer):
        return serializer.validated_data.get("template")

    filterset_fields = [
        "id",
        "name",
        "target",
        "retrieval_method",
        "retrieval_output",
        "template",
    ]
