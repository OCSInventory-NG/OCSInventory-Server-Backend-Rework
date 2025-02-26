from auth.auth_config.models import AuthConfig
from django.contrib.auth.models import User
from ocsinventory_backend.ocs_framework.viewsets import ExpandableFieldsMixin
from rest_framework.serializers import ModelSerializer
from .models import AuthMapping


class AuthMappingSerializer(ExpandableFieldsMixin, ModelSerializer):
    """
    This serialize class provide the API representation
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthMapping
        fields = [
            "id",
            "auth_config",
            "internal_field",
            "external_field",
        ]

        expandable_fields = {}

    def custom_validate(self, data):
        """
        Perform custom validation on the AuthMapping data.
        Custom validation applies to specific fields:
        - internal_field
        - external_field

        The logic is as follows:
        - internal_field must be unique for a given auth_config and linked to a
            valid field in the user model
        - external_field can be reused for different internal_field
        """
        # check if either internal_field or external_field is in the data
        if "internal_field" in data or "external_field" in data:
            # try to get 'auth_config' from data, parent or instance
            auth_config = data.get("auth_config")
            if not auth_config:
                # If 'auth_config' is not in data, try to get it from parent
                if self.instance:
                    data["auth_config"] = self.instance.auth_config
                else:
                    auth_config_id = self.parent.parent.parent.initial_data[
                        "auth_config_id"
                    ]
                    data["auth_config"] = AuthConfig.objects.get(pk=auth_config_id)

                auth_config = data["auth_config"]

            # check if the internal_field is unique for the auth_config
            if "internal_field" in data:
                internal_field = data["internal_field"]
                existing_mapping = AuthMapping.objects.filter(
                    auth_config=auth_config, internal_field=internal_field
                ).exclude(pk=self.instance.pk if self.instance else None)
                if existing_mapping.exists():
                    raise serializers.ValidationError(
                        f"Internal field '{internal_field}' is already mapped to "
                        f"external field '{existing_mapping.first().external_field}' "
                        f"for auth_config '{auth_config}'"
                    )

                # is internal_field a valid field in the user model ?
                # we use the default django user model
                user_model = User
                if not hasattr(user_model, internal_field):
                    raise serializers.ValidationError(
                        f"Internal field '{internal_field}' is not a valid field in "
                        f"the user model '{user_model}'"
                    )
        return data

    def create(self, validated_data):
        """
        Overriding the create method
        """
        # custom validation
        validated_data = self.custom_validate(validated_data)
        return AuthMapping.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        Overriding the update method
        """
        # custom validation
        validated_data = self.custom_validate(validated_data)
        return super().update(instance, validated_data)
