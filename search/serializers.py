from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from search.models import Search
from user.serializers import UserSerializer


class SearchSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Search
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
        expandable_fields = {"user": UserSerializer, "groups": GroupSerializer}


class SearchConditionSerializer(serializers.Serializer):
    """
    One search condition, as sent in a search_data AND-group.

    Example:
    {"object": "software_dictionary_entries", "route": "software_dictionary",
     "field": "name", "fieldtype": "string", "operator": "iexact",
     "value": "Git", "link": "AND"}
    """

    object = serializers.CharField(
        help_text="Target model key, e.g. 'InventoryBase', 'AccountinfoConfig', "
        "'results', 'logs', 'snmpscanner', 'inventory_sections', "
        "'software_dictionary_entries'."
    )
    route = serializers.CharField(
        required=False, help_text="Frontend route associated with the condition."
    )
    field = serializers.CharField(help_text="Field name to filter on.")
    fieldtype = serializers.CharField(
        required=False,
        help_text="Field type hint, e.g. 'string', 'select', 'checkbox'.",
    )
    operator = serializers.CharField(
        help_text="Lookup operator, e.g. 'exact', 'iexact', 'icontains', "
        "'istartswith', 'iendswith'."
    )
    value = serializers.JSONField(help_text="Value to compare the field against.")
    link = serializers.ChoiceField(
        choices=["AND", "OR"],
        default="AND",
        help_text="How this condition links to the previous one.",
    )
    section = serializers.CharField(
        required=False,
        help_text="Template section id, required when object is "
        "'inventory_sections'.",
    )


class SearchRequestSerializer(serializers.Serializer):
    """
    Payload accepted by POST /search/.

    search_data is a list of AND-groups; groups are combined using each
    group's first condition 'link' (AND/OR).
    """

    search_data = serializers.ListField(
        child=serializers.ListField(child=SearchConditionSerializer()),
        default=list,
        help_text="List of AND-condition groups to combine into the search query.",
    )
    grouped = serializers.BooleanField(
        default=True,
        help_text="If true, results are grouped by asset with a single matched "
        "row per relation.",
    )
    ungroup = serializers.BooleanField(
        default=False,
        help_text="If true, one row is returned per matched related record "
        "instead of one per asset.",
    )


class SearchErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
