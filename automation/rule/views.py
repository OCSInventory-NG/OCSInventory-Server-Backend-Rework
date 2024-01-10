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

    def list(self):
        """List all the triggers and the related models"""
        trigger_data = []
        for trigger, _ in Rule.TRIGGER_CHOICES:
            model_name = self.get_model_name_for_trigger(trigger)
            targets = self.get_trigger_targets(trigger, model_name)
            trigger_data.append(
                {
                    "trigger": trigger,
                    "model_name": model_name,
                    "action_targets": targets,
                }
            )

        return Response(trigger_data, status=status.HTTP_200_OK)

    def get_model_name_for_trigger(self, trigger):
        """Return the model name and the app name for the given trigger"""
        model_mapping = {
            "inventory_received": "inventory_base.InventoryBase",
            "user_login": "auth.User",
            "netdevice_received": "netdevice.Netdevice",
        }
        model_path = model_mapping.get(trigger, "default.Model")
        model = apps.get_model(model_path)
        app_name = model._meta.app_label

        model_name = f"{app_name}.{model.__name__}"

        return model_name

    def get_trigger_targets(self, trigger, model):
        """Return the models on which an action can be executed for the given
        trigger, i.e. the models related to the main model (ForeignKey,
        ManyToManyField)
        """
        targets = {}
        model_obj = apps.get_model(model)
        for field in model_obj._meta.get_fields():
            if field.is_relation:
                # ignore ManyToOne relations
                if not field.many_to_one:
                    app_name = field.related_model._meta.app_label
                    model_name = field.related_model.__name__
                    model_name = f"{app_name}.{model_name}"
                    targets[trigger] = targets.get(trigger, []) + [model_name]

        # manually add accountinfo config
        targets[trigger] = targets.get(trigger, []) + ["accountinfo.AccountinfoConfig"]
        # also adding the model itself
        targets[trigger] = targets.get(trigger, []) + [str(model)]

        return targets.get(trigger, [])
