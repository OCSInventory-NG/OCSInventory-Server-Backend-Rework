from deployment.action.models import DeploymentAction
from django.db.models import F
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer


class ActionSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serializer class provides the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = DeploymentAction
        fields = [
            "id",
            "package",
            "name",
            "priority",
            "date_created",
            "action_type",
            "command",
            "file",
            "original_file_name",
        ]
        extra_kwargs = {
            "file": {"required": False},
            "original_file_name": {"required": False},
        }

        expandable_fields = {}

    def custom_validate(self, data):
        """
        Perform custom validation on the DeploymentAction data.
        """
        if (
            DeploymentAction.objects.filter(package=data["package"])
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            # adjust priorities if there's a conflict
            # if the current priority is being updated to a higher priority
            if self.instance and data["priority"] < self.instance.priority:

                DeploymentAction.objects.filter(
                    package=data["package"],
                    priority__lt=self.instance.priority,
                    priority__gte=data["priority"],
                ).exclude(pk=self.instance.pk if self.instance else None).update(
                    priority=F("priority") + 1
                )

            # if the current priority is being updated to a lower priority
            elif self.instance and data["priority"] > self.instance.priority:
                DeploymentAction.objects.filter(
                    package=data["package"],
                    priority__lte=data["priority"],
                    priority__gt=self.instance.priority,
                ).exclude(pk=self.instance.pk if self.instance else None).update(
                    priority=F("priority") - 1
                )
            # adjust priorities of existing configs
            else:
                DeploymentAction.objects.filter(
                    package=data["package"], priority__gte=data["priority"]
                ).update(priority=F("priority") + 1)
        return data

    def create(self, validated_data):
        """
        Overriding the create method to manage action priority.
        """
        validated_data["priority"] = (
            DeploymentAction.objects.filter(package=validated_data["package"]).count()
            + 1
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Overriding the update method to manage action priority.
        """
        validated_data = self.custom_validate(validated_data)
        return super().update(instance, validated_data)
