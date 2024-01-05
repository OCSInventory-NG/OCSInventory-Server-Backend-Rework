from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from automation.rule.models import Rule, Action
from automation.rule.serializers import RuleSerializer, ActionSerializer


class RuleViewSet(viewsets.OCSViewSet):
    """
    Rule viewset
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Rule.objects.all()
    serializer_class = RuleSerializer
    model = Rule

    filterset_fields = ['id', 'trigger', 'actions']


class ActionViewSet(viewsets.OCSViewSet):
    """
    Action viewset
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    model = Action
