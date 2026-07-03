from inventory.field.models import Field
from inventory.field.serializers import FieldSerializer
from inventory.template.views import TemplateVersionSnapshotMixin
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class FieldViewSet(TemplateVersionSnapshotMixin, viewsets.OCSViewSet):
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

    def get_versioned_template(self, instance):
        return instance.section.template

    def get_versioned_template_for_create(self, serializer):
        section = serializer.validated_data.get("section")
        return section.template if section else None

    filterset_fields = [
        "id",
        "name",
        "retrieval_value",
        "override_target",
        "new_target",
        "retrieval_method",
        "retrieval_output",
        "section",
        "order",
    ]
