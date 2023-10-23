from django_cas_ng.backends import CASBackend
import logging
from django.conf import settings

from auth.auth_config.models import AuthConfig
from auth.auth_mapping.models import AuthMapping


class CustomCASBackend(CASBackend):
    """
    This backend extends the CASBackend from django-cas-ng to allow
    for dynamic configuration of the CAS server.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        super(CustomCASBackend, self).__init__()
        self.configs = AuthConfig.objects.filter(auth_method__name="CAS",
                                                 enabled=True).order_by("priority")
        self.mappings = AuthMapping.objects.filter(auth_method__name="CAS",
                                                   auth_config__auth_method__name="CAS")

    def authenticate(self, request, ticket, service):
        print("CustomCASBackend.authenticate")
        # TODO : get the first enabled config for now but figure out how to handle multiple configs (or prevent it)
        cas_config = self.configs[0]

        # TODO : better way to set settings ?
        settings.CAS_SERVER_URL = cas_config.config['SERVER_URL']
        settings.CAS_LOGIN_URL = cas_config.config['SERVER_URL'] + cas_config.config['LOGIN_ROUTE']
        settings.CAS_LOGOUT_URL = cas_config.config['SERVER_URL'] + cas_config.config['LOGOUT_ROUTE']

        # try to authenticate the user
        casBackend = CASBackend()
        user = casBackend.authenticate(request=request, ticket=ticket, service=service)

        if user is not None:
            return user

        # no match found
        return None
