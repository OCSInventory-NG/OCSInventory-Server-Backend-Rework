from django.contrib.auth.models import Group
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class GroupSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Group
        fields = ["id", "name", "permissions"]
        expandable_fields = {}
