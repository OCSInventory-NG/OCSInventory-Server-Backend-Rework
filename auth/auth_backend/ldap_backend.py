from django_auth_ldap.backend import LDAPBackend
from django_auth_ldap.config import LDAPSearch
import ldap
import logging

from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping


class CustomLDAPBackend(LDAPBackend):
    """
    This backend extends the LDAPBackend from django-auth-ldap to allow
    dynamic configuration of the LDAP server.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        super(CustomLDAPBackend, self).__init__()
        # get all LDAP config from database
        self.configs = AuthConfig.objects.filter(auth_method__name="LDAP",
                                                 enabled=True).order_by("priority")
        # and mappings
        self.mappings = AuthMapping.objects.filter(auth_config__enabled=True,
                                                   auth_config__auth_method__name="LDAP"
                                                   )

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            for config in self.configs:
                # set settings
                self.settings.SERVER_URI = config.config["SERVER_URI"]
                self.settings.BIND_DN = config.config["BIND_DN"]
                self.settings.BIND_PASSWORD = config.config["BIND_PASSWORD"]
                self.settings.MIRROR_GROUPS = config.config['MIRROR_GROUPS']

                self.settings.USER_SEARCH = LDAPSearch(
                    config.config['BASE_DN'],
                    ldap.SCOPE_SUBTREE,
                    f"({config.config['USER_LOGIN_FIELD']}=%(user)s)"
                )

                self.defineMapping(config)
                ldap.set_option(ldap.OPT_PROTOCOL_VERSION,
                                config.config['PROTOCOL_VERSION'])

                # attempt authentication
                user = super(CustomLDAPBackend,
                             self).authenticate(request,
                                                username=username,
                                                password=password,
                                                **kwargs)

                if user:
                    return user

        except Exception as e:
            self.logger.exception(e)
            return None

    def defineMapping(self, config):
        for mapping in self.mappings:
            self.settings.USER_ATTR_MAP[
                mapping.internal_field] = mapping.external_field

        # if empty mapping is defined, inform user
        if len(self.settings.USER_ATTR_MAP) == 0:
            self.logger.info(
                f"LDAP config {config.id} has no mapping defined")

    def get_config_fields(self):
        """
        Return the list of fields to be used in the 'config' field of the
        AuthConfig model.
        """
        return ['SERVER_URI', 'BIND_DN', 'BIND_PASSWORD', 'BASE_DN',
                'USER_LOGIN_FIELD', 'PROTOCOL_VERSION', 'MIRROR_GROUPS']
