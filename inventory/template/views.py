from django.db import transaction
from django.shortcuts import get_object_or_404
from inventory.section.serializers import SectionSerializer
from inventory.template.models import Template, TemplateVersion
from inventory.template.serializers import (
    TemplateExportSerializer,
    TemplateSerializer,
    TemplateVersionListSerializer,
    TemplateVersionSerializer,
)
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

    def perform_create(self, serializer):
        """
        Creating a template also takes its one and only automatic snapshot;
        every other version is created manually from then on (see the
        `versions` action below).
        """
        super().perform_create(serializer)
        TemplateVersion.create_snapshot(
            serializer.instance, self.request.user, label="Initial version"
        )

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

    @action(detail=True, methods=["get", "post"], url_path="versions")
    def versions(self, request, pk=None):
        """List the version history for this template"""
        template = self.get_object()

        if request.method == "POST":
            version = TemplateVersion.create_snapshot(
                template, request.user, label=request.data.get("label", "")
            )
            serializer = TemplateVersionListSerializer(version)
            return Response(serializer.data, status=201)

        queryset = template.versions.all()
        page = self.paginate_queryset(queryset)
        serializer = TemplateVersionListSerializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get", "delete"],
        url_path=r"versions/(?P<version_id>[^/.]+)",
    )
    def version_detail(self, request, pk=None, version_id=None):
        """Retrieve a single version, including its full snapshot, or delete it"""
        template = self.get_object()
        version = get_object_or_404(TemplateVersion, pk=version_id, template=template)

        if request.method == "DELETE":
            if version.revision == 1:
                return Response(
                    {"error": "The initial version of a template cannot be deleted"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            version.delete()
            return Response(status=204)

        serializer = TemplateVersionSerializer(version)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"versions/(?P<version_id>[^/.]+)/rollback",
    )
    def rollback(self, request, pk=None, version_id=None):
        """Restore the template to the state captured in a previous version"""
        template = self.get_object()
        version = get_object_or_404(TemplateVersion, pk=version_id, template=template)

        with transaction.atomic():
            template.sections.all().delete()
            template.name = version.snapshot["name"]
            template.os = version.snapshot["os"]
            template.is_protected = version.snapshot["is_protected"]
            template.save()

            for section_data in version.snapshot.get("sections", []):
                section_serializer = SectionSerializer(
                    data={**section_data, "template": template.id}
                )
                section_serializer.is_valid(raise_exception=True)
                section_serializer.save()

        serializer = self.get_serializer(template)
        return Response(serializer.data)
