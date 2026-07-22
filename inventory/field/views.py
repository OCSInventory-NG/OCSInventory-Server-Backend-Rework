from django_filters import rest_framework as filters
from inventory.field.models import Field
from inventory.field.serializers import FieldSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class FieldFilterSet(filters.FilterSet):
    """
    Filter fields by section through a plain id lookup instead of the strict
    ModelChoiceFilter django-filter would build for the FK. A stale reference
    (e.g. a saved search / dynamic group pointing at a section that no longer
    exists) then returns an empty list instead of a 400 "Select a valid choice"
    that breaks the group editor.
    """

    section = filters.NumberFilter(field_name="section_id")

    class Meta:
        model = Field
        fields = [
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


class FieldViewSet(viewsets.OCSViewSet):
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

    filterset_class = FieldFilterSet
