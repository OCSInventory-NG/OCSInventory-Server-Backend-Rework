from inventory.template.models import Template
from inventory.template.serializers import TemplateExportSerializer, TemplateSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.decorators import action
from rest_framework.response import Response


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

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        """
        Export a template and its nested sections and fields, using specific
        serializers to strip ids and fk relations
        """
        obj = self.get_object()
        ser = TemplateExportSerializer(obj, context=self.get_serializer_context())
        data = dict(ser.data)
        data["is_protected"] = False
        # schema version for easy compat w/ import if the format/model changes
        payload = {"schema_version": 1, **data}
        resp = Response(payload)
        return resp
