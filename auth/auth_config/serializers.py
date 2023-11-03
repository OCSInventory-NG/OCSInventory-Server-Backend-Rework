from rest_framework import serializers
from .models import AuthConfig
from auth.auth_backend.ldap_backend import CustomLDAPBackend
from auth.auth_backend.cas_backend import CustomCASBackend
from auth.auth_backend.oidc_backend import CustomOIDCBackend


class AuthConfigSerializer(serializers.ModelSerializer):
    """
    This serialize class provide the API representation

    Args:
        serializers ([ModelSerializer])
    """

    class Meta:
        """Define the linked model and the fields registered in the API"""

        model = AuthConfig
        fields = '__all__'

    def validate(self, data):
        """
        Perform custom validation on the AuthConfig data.
        """
        # validate CONFIG based on auth_method
        auth_method = data.get('auth_method')

        if auth_method and data.get('config'):
            self.config_validate(data)

        # TODO : enforce priority constraints for multiple enabled configs

        return data

    def config_validate(self, data):
        """
        Validate the config by checking if all required fields are present.
        Required fields are defined in the backend class.
        """
        backend_classes = {
            'CAS': CustomCASBackend,
            'OIDC': CustomOIDCBackend,
            'LDAP': CustomLDAPBackend,
        }

        auth_method = data.get('auth_method')
        if not auth_method or auth_method.name not in backend_classes:
            raise serializers.ValidationError("Invalid or missing "
                                              "authentication method.")

        # instantiate the correct backend
        backend = backend_classes[auth_method.name]()
        required_fields = set(backend.get_config_fields())

        provided_fields = set(data['config'].keys())

        # missing fields
        missing_fields = required_fields - provided_fields
        if missing_fields:
            err_msg = f"Missing configuration fields: {', '.join(missing_fields)}"
            raise serializers.ValidationError(err_msg)
