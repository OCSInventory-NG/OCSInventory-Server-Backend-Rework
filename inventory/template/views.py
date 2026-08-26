from django.db import transaction
from django.shortcuts import get_object_or_404
from inventory.category.models import Category
from inventory.field.models import Field
from inventory.section.models import Section
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

    TEMPLATE_ATTRS = ["name", "os", "is_protected"]
    SECTION_ATTRS = [
        "name",
        "retrieval_method",
        "retrieval_output",
        "target",
        "options",
        "is_active",
    ]
    FIELD_ATTRS = [
        "name",
        "order",
        "retrieval_value",
        "override_target",
        "new_target",
        "retrieval_method",
        "retrieval_output",
        "options",
    ]

    def perform_create(self, serializer):
        """
        Creating a protected template also takes its one and only automatic
        snapshot; every other version is created manually from then on (see
        the `versions` action below). Regular templates are created empty, so
        an automatic initial version would just capture an empty snapshot and
        is skipped.
        """
        super().perform_create(serializer)
        if serializer.instance.is_protected:
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
            if template.is_protected and version.revision == 1:
                return Response(
                    {"error": "The initial version of a template cannot be deleted"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            version.delete()
            return Response(status=204)

        serializer = TemplateVersionSerializer(version)
        return Response(serializer.data)

    @staticmethod
    def _diff(current_objs, snapshot_dicts):
        """
        Pair current model instances with snapshot dicts so unchanged entities
        keep their primary key.
        """
        by_id = {obj.pk: obj for obj in current_objs}
        used = set()
        matched = []
        unmatched_snaps = []

        # Pass 1: match on id (robust to renames)
        for snap in snapshot_dicts:
            snap_id = snap.get("id")
            obj = by_id.get(snap_id) if snap_id is not None else None
            if obj is not None and obj.pk not in used:
                matched.append((obj, snap))
                used.add(obj.pk)
            else:
                unmatched_snaps.append(snap)

        # Pass 2: match the rest on name (legacy snapshots without ids)
        remaining_by_name = {}
        for obj in current_objs:
            if obj.pk not in used:
                remaining_by_name.setdefault(obj.name, []).append(obj)

        to_create = []
        for snap in unmatched_snaps:
            bucket = remaining_by_name.get(snap["name"])
            if bucket:
                obj = bucket.pop(0)
                matched.append((obj, snap))
                used.add(obj.pk)
            else:
                to_create.append(snap)

        to_delete = [obj for obj in current_objs if obj.pk not in used]
        return matched, to_create, to_delete

    @staticmethod
    def _apply(instance, snap, attrs):
        """
        Copy the snapshot attributes onto an existing instance and save it only
        if at least one value actually changed. Skipping no-op saves avoids
        bumping the template's last_update (via the Section/Field post_save
        signals) and marking untouched sections/fields as modified.
        """
        changed = False
        for attr in attrs:
            value = snap.get(attr)
            if getattr(instance, attr) != value:
                setattr(instance, attr, value)
                changed = True
        if changed:
            instance.save()
        return changed

    @staticmethod
    def _restore_categories(section, category_ids):
        """
        Restore the section's category links (the Category.inventory_sections
        M2M) to the set captured in the snapshot. Categories that no longer
        exist are ignored, and the M2M is only rewritten when it actually
        differs to avoid needless churn.
        """
        categories = list(Category.objects.filter(id__in=category_ids))
        desired = {category.id for category in categories}
        current = set(section.category_set.values_list("id", flat=True))
        if desired != current:
            section.category_set.set(categories)

    def _restore_fields(self, section, snapshot_fields):
        matched, to_create, to_delete = self._diff(
            list(section.fields.all()), snapshot_fields
        )
        # Delete first: Field's post_delete signal re-numbers sibling orders,
        # so the explicit orders set below must be applied afterwards.
        for field in to_delete:
            field.delete()
        for field, snap in matched:
            self._apply(field, snap, self.FIELD_ATTRS)
        for snap in to_create:
            Field.objects.create(
                section=section, **{attr: snap.get(attr) for attr in self.FIELD_ATTRS}
            )

    def _create_section(self, template, snap):
        section = Section.objects.create(
            template=template, **{attr: snap.get(attr) for attr in self.SECTION_ATTRS}
        )
        if "categories" in snap:
            self._restore_categories(section, snap["categories"])
        for field_snap in snap.get("fields", []):
            Field.objects.create(
                section=section,
                **{attr: field_snap.get(attr) for attr in self.FIELD_ATTRS},
            )

    def _restore_sections(self, template, snapshot_sections):
        matched, to_create, to_delete = self._diff(
            list(template.sections.all()), snapshot_sections
        )
        for section in to_delete:
            section.delete()
        for section, snap in matched:
            self._apply(section, snap, self.SECTION_ATTRS)
            if "categories" in snap:
                self._restore_categories(section, snap["categories"])
            self._restore_fields(section, snap.get("fields", []))
        for snap in to_create:
            self._create_section(template, snap)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"versions/(?P<version_id>[^/.]+)/rollback",
    )
    def rollback(self, request, pk=None, version_id=None):
        """
        Restore the template to the state captured in a previous version.
        """
        template = self.get_object()
        version = get_object_or_404(TemplateVersion, pk=version_id, template=template)
        snapshot = version.snapshot

        with transaction.atomic():
            self._apply(template, snapshot, self.TEMPLATE_ATTRS)
            self._restore_sections(template, snapshot.get("sections", []))

        serializer = self.get_serializer(template)
        return Response(serializer.data)
