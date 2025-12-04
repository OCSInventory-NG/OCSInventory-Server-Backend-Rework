from django_cas_ng.backends import CASBackend
import logging
from django.conf import settings

from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping


class CustomCASBackend(CASBackend):
    """
    This backend extends the CASBackend from django-cas-ng to allow
    for dynamic configuration of the CAS server.

    Note : contrary to OIDC, CAS does not provide a way to choose which field from
    the user model to use for reconciliation. The default is username.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        super(CustomCASBackend, self).__init__()
        # fetch configurations and mappings
        self.configs = AuthConfig.objects.filter(auth_method__name="CAS",
                                                 enabled=True).order_by("priority")
        self.mappings = AuthMapping.objects.filter(auth_config__enabled=True,
                                                   auth_config__auth_method__name="CAS")
        # TODO: get the first enabled config for now but figure out
        # how to handle multiple configs (or prevent it)
        cas_config = self.configs[0]
        self.current_config = cas_config
        login_url = cas_config.config['SERVER_URL'] + cas_config.config['LOGIN_ROUTE']
        logout_url = cas_config.config['SERVER_URL'] + cas_config.config['LOGOUT_ROUTE']

        # update settings
        settings.CAS_SERVER_URL = cas_config.config['SERVER_URL']
        settings.CAS_LOGIN_URL = login_url
        settings.CAS_LOGOUT_URL = logout_url
        settings.CAS_VERSION = cas_config.config['VERSION']
        # which field to use for reconciliation (CAS side)
        # using the mapping for internal field username
        # if empty mapping is defined, inform user
        if len(self.mappings) == 0:
            self.logger.debug(
                f"CAS config {cas_config.id} has no mapping defined")
        else:
            settings.CAS_USERNAME_ATTRIBUTE = self.mappings.get(
                                                               internal_field="username"
                                                                ).external_field
            # build the CAS_RENAME_ATTRIBUTES from mappings
            settings.CAS_RENAME_ATTRIBUTES = {mapping.external_field: mapping.
                                              internal_field for mapping
                                              in self.mappings}
            # allow attributes to be applied to the user
            settings.CAS_APPLY_ATTRIBUTES_TO_USER = True

        # TODO: handle SSL verification
        # settings.CAS_VERIFY_SSL_CERTIFICATE = True

    def authenticate(self, request, ticket, service):
        # try to authenticate the user
        user = super().authenticate(request=request, ticket=ticket, service=service)

        if user is not None:
            attributes = {}
            if request:
                attributes = request.session.get("attributes", {}) or {}
            metadata = {
                "authenticationMethod": attributes.get("authenticationMethod"),
                "attributes": attributes,
            }
            user._auth_context_data = {
                "auth_method": self.current_config.auth_method,
                "auth_config": self.current_config,
                "metadata": metadata,
            }
            return user

        # no match found
        return None

    @staticmethod
    def get_config_fields():
        """
        Return the list of fields to be used in the 'config' field of the
        AuthConfig model.
        """
        return ['SERVER_URL', 'LOGIN_ROUTE', 'LOGOUT_ROUTE', 'VERSION', 'AUTO_REDIRECT']
