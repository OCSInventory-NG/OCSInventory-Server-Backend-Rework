from django.db import transaction
from inventory.section.serializers import SectionSerializer
from inventory.template.models import Template
from inventory.template.serializers import TemplateExportSerializer, TemplateSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import status
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

    @action(detail=True, methods=["post"], url_path="import-sections")
    def import_sections(self, request, pk=None):
        """
        Import (append) one or more sections, with their nested fields, into an
        existing template. Used by the partial template import: the sections
        come from an exported template file and are attached as brand new
        sections, so any provided id is dropped and the template is forced to
        the target one.
        """
        template = self.get_object()

        payload = request.data
        sections = payload.get("sections") if isinstance(payload, dict) else payload
        if not isinstance(sections, list) or not sections:
            return Response(
                {"error": "No section to import"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = []
        for section in sections:
            if not isinstance(section, dict):
                return Response(
                    {"error": "Invalid section format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item = {key: value for key, value in section.items() if key != "id"}
            item["template"] = template.pk
            data.append(item)

        serializer = SectionSerializer(
            data=data, many=True, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()

        return Response(
            self.get_serializer(template).data,
            status=status.HTTP_201_CREATED,
        )
