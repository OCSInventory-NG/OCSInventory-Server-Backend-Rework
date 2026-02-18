from extension.models import Extension
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class ExtensionSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Extension
        fields = [
            "id",
            "name",
            "description",
            "version",
            "author",
            "enabled",
            "django_app",
        ]
