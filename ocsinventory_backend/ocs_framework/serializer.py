from ocsinventory_backend.ocs_framework.models import OCSViewSetModel
from rest_framework import serializers


class OCSViewSetSerializer(serializers.ModelSerializer):
    """
    Serializer class for OCSView

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = OCSViewSetModel

        http_method_names = ["get", "post", "patch", "delete"]

    def to_representation(self, instance):
        """
        Customize the representation to include additional fields
        based on the 'accountinfo' URL parameter.
        """
        representation = super().to_representation(instance)

        request = self.context.get("request")

        if not request:
            return representation

        else:
            return representation
