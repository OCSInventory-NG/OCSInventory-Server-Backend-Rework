from automation.rule.context import get_resolver_for_trigger
from automation.rule.models import Action, Rule
from automation.rule.serializers import (
    ActionSerializer,
    RuleSerializer,
    TriggerSerializer,
)
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import status
from rest_framework.response import Response


class RuleViewSet(viewsets.OCSViewSet):
    """
    Rule viewset
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Rule.objects.all()
    serializer_class = RuleSerializer
    model = Rule

    filterset_fields = ["id", "trigger", "priority", "actions"]


class ActionViewSet(viewsets.OCSViewSet):
    """
    Action viewset
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    model = Action
    filterset_fields = [
        "id",
        "rule",
        "priority",
        "action",
        "description",
        "content_type",
        "object_id",
        "object_slug",
        "field",
    ]


class TriggerViewSet(viewsets.OCSViewSet):
    """
    Trigger viewset
    """

    permission_classes = []
    queryset = Rule.TRIGGER_CHOICES

    allowed_methods = ["GET"]

    model_mapping = {
        "inventory_received": "inventory_base.inventorybase",
        "user_login": "auth.user",
        "netdevice_received": "netdevice.netdevice",
    }

    target_mapping = {
        "inventory_received": {
            "inventory_base.inventorybase": ["template"],
            "accountinfo.accountinfoconfig": [],
        },
        "user_login": {
            "auth.user": ["groups"],
        },
        "netdevice_received": {
            "accountinfo.accountinfoconfig": [],
        },
    }

    def list(self, request, *args, **kwargs):
        """List all the triggers and the related models"""
        trigger_data = []
        for trigger, _ in Rule.TRIGGER_CHOICES:
            model_name = self.model_mapping[trigger]
            targets = self.target_mapping[trigger]
            resolver = get_resolver_for_trigger(trigger)
            trigger_data.append(
                {
                    "trigger": trigger,
                    "model_name": model_name,
                    "action_targets": targets,
                    "context_fields": resolver.get_schema(),
                }
            )

        serializer = TriggerSerializer(trigger_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
