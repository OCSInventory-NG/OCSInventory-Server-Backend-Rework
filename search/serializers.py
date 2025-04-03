from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
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
