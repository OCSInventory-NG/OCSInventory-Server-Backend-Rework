from deployment.action.models import Action
from deployment.action.serializers import ActionSerializer
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


class ActionViewSet(viewsets.OCSViewSet):
    """
    View behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    model = Action
    filterset_fields = ['id', 'package', 'name', 'priority', 'date_created',
                        'action_type', 'command', 'output']
