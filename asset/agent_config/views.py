from config.models import Config
from config.serializers import ConfigSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework.response import Response


class AgentConfigViewSet(viewsets.OCSViewSet):
    """
    Allow read of agent config
    This view is reachable at the /asset/configs/ endpoint.

    GET:
    List agent configuration
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]
    queryset = Config.objects.all()
    allowed_methods = ["GET"]

    def list(self, request, *args, **kwargs):
        queryset = self.queryset.filter(name__in=["agent", "deployment"])
        serializer = ConfigSerializer(queryset, many=True)
        return Response(serializer.data, status=200)
