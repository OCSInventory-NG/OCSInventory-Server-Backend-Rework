from automation.rule.models import Action, Rule
from automation.rule.serializers import ActionSerializer, RuleSerializer
from django.apps import apps
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

    filterset_fields = ["id", "trigger", "actions"]


class ActionViewSet(viewsets.OCSViewSet):
    """
    Action viewset
    """

    permission_classes = [DefaultModelPermissions]

    queryset = Action.objects.all()
    serializer_class = ActionSerializer
    model = Action


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
        }
    }

    def list(self, request, *args, **kwargs):
        """List all the triggers and the related models"""
        trigger_data = []
        for trigger, _ in Rule.TRIGGER_CHOICES:
            model_name = self.model_mapping[trigger]
            targets = self.target_mapping[trigger]
            trigger_data.append(
                {
                    "trigger": trigger,
                    "model_name": model_name,
                    "action_targets": targets,
                }
            )

        return Response(trigger_data, status=status.HTTP_200_OK)
