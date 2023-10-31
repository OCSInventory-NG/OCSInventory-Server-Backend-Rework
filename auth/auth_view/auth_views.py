import logging
from typing import Any
from urllib.parse import quote, urlencode
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.contrib.auth import login
from django.urls import reverse
from django.views import View
from rest_framework.authtoken.models import Token

from auth.auth_backend.cas_backend import CustomCASBackend
from auth.auth_backend.oidc_backend import CustomOIDCBackend

from auth.auth_method.models import AuthMethod
from auth.auth_config.models import AuthConfig


class BaseAuthView(View):
    """
    Base view for authentication, to be inherited by LoginView and CallbackView.
    Retrieves enabled auth methods, configs and mappings.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # authentication methods we're interested in
        methods = ["OIDC", "CAS"]

        # get enabled auth methods based on priority
        self.auth_methods = AuthMethod.objects.filter(
            enabled=True,
            priority__gte=0,
            name__in=methods
        )

        # get enabled auth configs for the above auth methods
        self.auth_configs = AuthConfig.objects.filter(
            enabled=True,
            auth_method__in=self.auth_methods
        )


class LoginView(BaseAuthView):
    """
    View to handle login requests.
    """

    def get(self, request, *args, **kwargs):
        """
        Verify if CAS or OIDC is enabled and configured and redirect to the
        appropriate login page.
        """
        # at this point auth_configs should only contain one config (because
        # multiple cannot be enabled), we check just in case
        if len(self.auth_methods) == 1:
            self.current_auth_config = self.auth_configs[0]
            # check if CAS is enabled
            if self.current_auth_config.auth_method.name == "CAS":
                return self.cas_login(request)
            # check if OIDC is enabled
            elif self.current_auth_config.auth_method.name == "OIDC":
                return self.oidc_login(request)

        # no CAS or OIDC config found : default login page
        return redirect("/")

    def cas_login(self, request):
        """Redirect to CAS login page"""
        cas_login_url = (self.current_auth_config.config['SERVER_URL'] +
                         self.current_auth_config.config['LOGIN_ROUTE'])
        service_url = request.build_absolute_uri(reverse('callback'))

        return redirect(cas_login_url + '?service=' + service_url)

    def oidc_login(self, request):
        """Redirect to OIDC login page"""
        params = {
            "response_type": "code",
            "client_id": self.current_auth_config.config['CLIENT_ID'],
            "redirect_uri": request.build_absolute_uri(reverse('callback')),
            "state": None,
            "scope": self.current_auth_config.config['SCOPES'],
        }
        query = urlencode(params, quote_via=quote)

        redirect_url = "{url}?{query}".format(
            url=self.current_auth_config.config['AUTHORIZATION_ENDPOINT'], query=query)
        return HttpResponseRedirect(redirect_url)


class CallbackView(BaseAuthView):
    """
    View to handle callback requests.
    """

    def get(self, request, *args, **kwargs):
        """Handle callback requests from CAS or OIDC"""
        ticket = request.GET.get('ticket')
        if ticket:
            return self.cas_callback(request)

        code = request.GET.get('code')
        if code:
            return self.oidc_callback(request)

    def cas_callback(self, request):
        """Handle CAS callback requests"""
        ticket = request.GET.get('ticket')
        service_url = request.build_absolute_uri()
        # pass the ticket to CustomCASBackend
        customCASBackend = CustomCASBackend()
        user = customCASBackend.authenticate(request, ticket, service_url)

        if user is not None:
            login(request, user)
            # Generate a token for the user
            token, created = Token.objects.get_or_create(user=user)
            # Include the token in the response
            return JsonResponse({'token_authentication': token.key})

        else:
            return HttpResponseRedirect("/")

    def oidc_callback(self, request):
        """Handle OIDC callback requests"""
        customOIDCBackend = CustomOIDCBackend()
        user = customOIDCBackend.authenticate(request)

        if user is not None:
            login(request, user)
            # Generate a token for the user
            token, created = Token.objects.get_or_create(user=user)
            # Include the token in the response
            return JsonResponse({'token_authentication': token.key})

        else:
            return HttpResponseRedirect("/")
