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
from rest_framework.decorators import action
from rest_framework.response import Response


class TemplateVersionSnapshotMixin:
    """
    Mixin for viewsets that mutate a Template's content (the template itself,
    or one of its sections/fields). Snapshots the parent template's state
    right before an existing object is changed or removed, so it can be
    listed/restored later via TemplateVersion.
    """

    def get_versioned_template(self, instance):
        raise NotImplementedError

    def get_versioned_template_for_create(self, serializer):
        """
        Return the parent Template to snapshot before a new object is added
        to it, or None to skip (e.g. when creating a Template itself, there
        is no pre-existing state to protect)
        """
        return None

    def perform_create(self, serializer):
        template = self.get_versioned_template_for_create(serializer)
        if template is not None:
            TemplateVersion.create_snapshot(template, self.request.user)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        TemplateVersion.create_snapshot(
            self.get_versioned_template(serializer.instance), self.request.user
        )
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        TemplateVersion.create_snapshot(
            self.get_versioned_template(instance), self.request.user
        )
        super().perform_destroy(instance)


class TemplateViewSet(TemplateVersionSnapshotMixin, viewsets.OCSViewSet):
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

    def get_versioned_template(self, instance):
        return instance

    def perform_create(self, serializer):
        super(TemplateVersionSnapshotMixin, self).perform_create(serializer)
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

    @action(detail=True, methods=["get"], url_path="versions")
    def versions(self, request, pk=None):
        """List the version history for this template"""
        template = self.get_object()
        queryset = template.versions.all()
        page = self.paginate_queryset(queryset)
        serializer = TemplateVersionListSerializer(
            page if page is not None else queryset, many=True
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path=r"versions/(?P<version_id>[^/.]+)")
    def version_detail(self, request, pk=None, version_id=None):
        """Retrieve a single version, including its full snapshot"""
        template = self.get_object()
        version = get_object_or_404(TemplateVersion, pk=version_id, template=template)
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

        version_date = (
            request.data.get("version_date")
            or f"{version.created_at:%d/%m/%Y %H:%M:%S %Z}"
        )

        with transaction.atomic():
            TemplateVersion.create_snapshot(
                template,
                request.user,
                label=f"Before rollback to the {version_date} version",
            )

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
