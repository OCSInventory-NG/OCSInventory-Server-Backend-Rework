from ipdiscover.netgroup.models import Netgroup
from ipdiscover.network.serializers import NetworkSerializer
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class NetgroupSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = Netgroup
        fields = ["id", "name", "description"]
        expandable_fields = {"networks": NetworkSerializer}
