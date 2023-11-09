from rest_framework import serializers
from django.db.models import F
from importlib import import_module
from auth.auth_mapping.models import AuthMapping
from auth.auth_method.models import AuthMethod

from ocsinventory_backend import settings
from .models import AuthConfig
from auth.auth_mapping.serializers import AuthMappingSerializer


class AuthConfigSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """
    mappings = AuthMappingSerializer(many=True, required=False)

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthConfig
        fields = [
            "id",
            "auth_method",
            "enabled",
            "priority",
            "config",
            "mappings",
        ]

    def custom_validate(self, data):
        """
        Perform custom validation on the AuthConfig data.
        Custom validation applies to specific fields:
        - enabled
        - priority
        - config
        
        The logic is as follows:
        - If SSO auth_method, only one config can be enabled at all times and 
            priority is ignored
        - If non-SSO auth_method, multiple configs can be enabled at the same time
            but priority must be unique
        - If config is provided, validate the config fields based on the auth_method
            backend class (see static method get_config_fields() in each backend class)
        """

        # check if either enabled, priority or config is in the data
        if 'enabled' in data or 'priority' in data or 'config' in data:
            # try to get 'auth_method' from data, parent or instance
            auth_method = data.get('auth_method')
            if not auth_method:
                # if 'auth_method' is not in data, try to get it from parent
                auth_method_id = self.parent.parent.initial_data['auth_method_id']
                if auth_method_id:
                    data['auth_method'] = AuthMethod.objects.get(pk=auth_method_id)
                elif self.instance:
                    data['auth_method'] = self.instance.auth_method


            if auth_method and 'config' in data:
                self.config_validate(data)

            # check auth_method type
            if auth_method.auth_type == 'SSO':
                # check if another SSO method is enabled
                if 'enabled' in data and data['enabled'] is True:
                    existing_sso = AuthConfig.objects.filter(
                        auth_method__auth_type='SSO', 
                        enabled=True,
                    ).exclude(pk=self.instance.pk if self.instance else None)
                    if existing_sso.exists():
                        raise serializers.ValidationError(
                            "Another SSO configuration is already enabled. "
                            "Please disable it before enabling a new one."
                        )
                
                # SSO configs cannot have a priority
                if 'priority' in data and data['priority'] is not None:
                    raise serializers.ValidationError(
                        "Priority is not applicable for SSO authentication methods. "
                        "Make sure the priority field is set to null."
                    )

            if auth_method.auth_type != 'SSO' and 'priority' in data and data['priority'] is not None:
                
                # retrieve the current priority
                current_priority = data['priority']
                
                # query to check for other configs with the same priority for the same auth_method
                existing_configs = AuthConfig.objects.filter(
                    auth_method=auth_method, 
                    priority=current_priority,
                ).exclude(pk=self.instance.pk if self.instance else None)
                
                if existing_configs.exists():
                    # adjust priorities if there's a conflict
                    # if the current priority is being updated to a higher priority
                    if self.instance and current_priority < self.instance.priority:

                        AuthConfig.objects.filter(
                            auth_method=auth_method,
                            priority__lt=self.instance.priority,
                            priority__gte=current_priority
                        ).exclude(
                            pk=self.instance.pk if self.instance else None
                            ).update(priority=F('priority') + 1)

                    # if the current priority is being updated to a lower priority
                    elif self.instance and current_priority > self.instance.priority:
                        AuthConfig.objects.filter(
                            auth_method=auth_method,
                            priority__lte=current_priority,
                            priority__gt=self.instance.priority
                        ).exclude(
                            pk=self.instance.pk if self.instance else None
                            ).update(priority=F('priority') - 1)
                    else:
                        # adjust priorities of existing configs
                        AuthConfig.objects.filter(
                            auth_method=auth_method,
                            priority__gte=current_priority
                        ).exclude(
                            auth_method__auth_type='SSO'
                            ).update(priority=F('priority') + 1)
                    
            elif (auth_method.auth_type != 'SSO' and data['priority'] is None 
                  and self.instance is None):
                raise serializers.ValidationError(
                    "Priority is required for non-SSO authentication methods."
                )

        return data

    def config_validate(self, data):
        """
        This is not a field-level validation, but a custom validation that involves 
        multiple fields (auth_method and config)
        Validate the config by checking if all required fields are present.
        Required fields are defined in the backend class.
        Available backend classes are defined in project settings 
        (OCS_CUSTOM_AUTH_BACKENDS) and dynamically imported using importlib.
        """
        backend_classes = settings.OCS_CUSTOM_AUTH_BACKENDS

        auth_method = data['auth_method']
        if not auth_method or auth_method.name not in backend_classes:
            raise serializers.ValidationError("Invalid or missing authentication method.")

        # dynamically import the backend class
        backend_module_path = backend_classes[auth_method.name]
        module_name, class_name = backend_module_path.rsplit('.', 1)
        module = import_module(module_name)
        backend_class = getattr(module, class_name)

        # get_config_fields is a static method
        required_fields = set(backend_class.get_config_fields())

        provided_fields = set(data['config'].keys())

        # check for missing fields
        missing_fields = required_fields - provided_fields
        if missing_fields:
            raise serializers.ValidationError(
                f"Missing required fields: {', '.join(missing_fields)}"
            )
            
    def create(self, validated_data):
        """
        Overriding the create method to handle nested AuthMapping creation.
        """
        # custom validation
        validated_data = self.custom_validate(validated_data)

        if "mappings" in validated_data.keys():
            # If mappings are present
            mappings = validated_data.pop("mappings")
            parent = super().create(validated_data)

            for mapping in mappings:
                mapping["auth_config"] = parent
            self.fields["mappings"].create(mappings)
        else:
            parent = super().create(validated_data)
        
        return parent
