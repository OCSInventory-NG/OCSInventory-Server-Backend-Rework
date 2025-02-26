from django.db.models import F
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer

from .models import AuthMethod
from auth.auth_config.serializers import AuthConfigSerializer


class AuthMethodSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthMethod
        fields = ["id", "name", "auth_type", "enabled", "priority", "configs"]
        expandable_fields = {
            "configs": AuthConfigSerializer,
        }

    def custom_validate(self, data):
        """
        Perform custom validation on the AuthMethod data.
        Custom validation applies to specific fields:
        - enabled
        - priority

        Two checks are performed:
        - If auth_type=SSO, only one method can be enabled
        - If auth_type=OTHER, PRIORITY must be unique

        NB: greater priority number = lower priority (1 is highest priority)
        """
        # PUT will trigger the below but also PATCH made on 'enabled' or 'priority'
        if "enabled" in data or "priority" in data:
            # partial update: get the current auth_type
            if self.instance:
                data["auth_type"] = (
                    data["auth_type"]
                    if "auth_type" in data
                    else self.instance.auth_type
                )

            # check if TYPE=SSO and enforce only one method enabled
            if data["auth_type"] == "SSO":
                if "enabled" in data and data["enabled"] is True:
                    existing_sso = AuthMethod.objects.filter(
                        auth_type="SSO", enabled=True
                    ).exclude(pk=self.instance.pk if self.instance else None)
                    if existing_sso.exists():
                        raise serializers.ValidationError(
                            "Another SSO method is already enabled. "
                            "Please disable it before enabling a new one."
                        )
                # SSO methods cannot have a priority
                if "priority" in data and data["priority"] is not None:
                    raise serializers.ValidationError(
                        "Priority is not applicable for SSO authentication methods. "
                        "Make sure the priority field is set to null."
                    )

            # check PRIORITY uniqueness for non-SSO methods
            if (
                data["auth_type"] != "SSO"
                and "priority" in data
                and data["priority"] is not None
            ):
                priority = data["priority"]
                # Check if there is an existing method with the same priority
                existing_method = (
                    AuthMethod.objects.filter(priority=priority)
                    .exclude(auth_type="SSO")
                    .exclude(pk=self.instance.pk if self.instance else None)
                    .first()
                )

                if existing_method:
                    # if the current priority is being updated to a higher priority
                    if self.instance and priority < self.instance.priority:
                        # decrease the priority of all methods with lower priority
                        AuthMethod.objects.filter(
                            priority__lt=self.instance.priority, priority__gte=priority
                        ).exclude(auth_type="SSO").update(priority=F("priority") + 1)

                    # if the current priority is being updated to a lower priority
                    elif self.instance and priority > self.instance.priority:
                        # increase the priority of all methods with higher priority
                        AuthMethod.objects.filter(
                            priority__lte=priority, priority__gt=self.instance.priority
                        ).exclude(auth_type="SSO").update(priority=F("priority") - 1)

                    # if adding a new method or changing priority
                    else:
                        # decrease the priority of all methods with priority equal to
                        # or higher than the current one
                        AuthMethod.objects.filter(priority__gte=priority).exclude(
                            auth_type="SSO"
                        ).update(priority=F("priority") + 1)
            elif (
                data["auth_type"] != "SSO"
                and "priority" in data
                and data["priority"] is None
                and self.instance is None
            ):
                raise serializers.ValidationError(
                    "Priority is required for non-SSO authentication methods."
                )

        return data

    def create(self, validated_data):
        """
        Overriding the create method to handle nested AuthConfig creation.
        """
        # custom validation
        validated_data = self.custom_validate(validated_data)
        if "configs" in validated_data.keys():
            # if authconfigs are present
            authconfigs = validated_data.pop("configs")
            parent = super().create(validated_data)

            for authconfig in authconfigs:
                authconfig["auth_method"] = parent
            self.fields["configs"].create(authconfigs)
        else:
            parent = super().create(validated_data)

        return parent

    def update(self, instance, validated_data):
        """
        Overriding the update method to handle nested AuthConfig creation.
        """
        # custom validation
        validated_data = self.custom_validate(validated_data)

        # TODO : handle nested AuthConfig update ?
        # for now we only update the AuthMethod and let the configs as is
        return super().update(instance, validated_data)
