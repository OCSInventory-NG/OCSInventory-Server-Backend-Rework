from django.contrib.auth.backends import ModelBackend
import logging

from auth.auth_method.models import AuthMethod
from auth.auth_backend.ldap_backend import CustomLDAPBackend


class AuthBackend:
    """
    This backend routes authentication requests to the appropriate backend
    based on enabled auth methods and priorities defined in auth_method
    """

    logger = logging.getLogger(__name__)

    # oidc and cas are handled earlier a custom view and do not need to be
    # handled here
    METHOD_TO_BACKEND = {
        "LOCAL": ModelBackend,
        "LDAP": CustomLDAPBackend,
    }

    def __init__(self):
        self.model_backend = ModelBackend()

    def authenticate(self, request, username=None, password=None, **kwargs):
        # retrieve all enabled auth methods in order of priority
        auth_methods = AuthMethod.objects.filter(
            enabled=True,
            priority__gte=0,
        ).order_by("priority")

        for auth_method in auth_methods:
            # get the backend class for the auth method
            BackendClass = self.METHOD_TO_BACKEND.get(auth_method.name)
            # skip if the backend class is not defined
            if not BackendClass:
                self.logger.warning(f"Auth method {auth_method.name} has no backend")
                continue

            # try authenticating with the backend
            backend = BackendClass()
            print(f"Authenticating with {auth_method.name} backend")
            user = backend.authenticate(request, username=username, password=password,
                                        **kwargs)
            if user:
                return user

        return None
