from search.models import Search
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class SearchSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Search
        fields = "__all__"
        extra_kwargs = {"last_updated": {"read_only": True}}
