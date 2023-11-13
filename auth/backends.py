import logging
from importlib import import_module

from auth.auth_method.models import AuthMethod
from ocsinventory_backend import settings


class AuthBackend:
    """
    This backend routes authentication requests to the appropriate backend
    based on enabled auth methods and priorities defined in auth_method
    """

    logger = logging.getLogger(__name__)

    # oidc and cas are handled earlier in a custom view and do not need to be
    # handled here
    METHOD_TO_BACKEND = {
        "LOCAL": "django.contrib.auth.backends.ModelBackend",
        # getting the backend class from the settings
        "LDAP": settings.OCS_CUSTOM_AUTH_BACKENDS["LDAP"],
    }

    def __init__(self):
        # dynamically import the backend classes with importlib
        for method, backend in self.METHOD_TO_BACKEND.items():
            try:
                module_path, class_name = backend.rsplit(".", 1)
                module = import_module(module_path)
                self.METHOD_TO_BACKEND[method] = getattr(module, class_name)

            except (ImportError, AttributeError) as e:
                self.logger.error(
                    f"Failed to import {backend} for {method} authentication "
                    f"method: {e}")


    def authenticate(self, request, username=None, password=None, **kwargs):
        # retrieve all enabled auth methods in order of priority
        auth_methods = AuthMethod.objects.filter(
            enabled=True,
            priority__gte=0,
            auth_type="OTHER"
        ).order_by("priority")

        for auth_method in auth_methods:
            # get the backend class for the auth method
            BackendClass = self.METHOD_TO_BACKEND.get(auth_method.name)

            # try authenticating with the backend
            backend = BackendClass()
            self.logger.debug(
                f"Attempting authentication with {auth_method.name} backend")
            user = backend.authenticate(request, username=username, password=password,
                                        **kwargs)
            if user:
                return user

        return None
