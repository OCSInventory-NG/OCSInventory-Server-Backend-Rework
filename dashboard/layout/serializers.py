from dashboard.layout.models import DashboardLayout
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class DashboardLayoutSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation.
    """

    class Meta:
        """
        Define the linked model and the fields registered in the API.
        """

        model = DashboardLayout
        fields = [
            "id",
            "visibility",
            "user",
            "groups",
            "allow_group_modification",
            "name",
            "layout",
        ]
        expandable_fields = {}
