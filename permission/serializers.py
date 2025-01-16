from django.contrib.auth.models import Permission
from ocsinventory_backend.ocs_framework.serializers import ExpandableSerializer


class PermissionSerializer(ExpandableSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ExpandableSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Permission
        fields = ["id", "name", "content_type", "codename"]
