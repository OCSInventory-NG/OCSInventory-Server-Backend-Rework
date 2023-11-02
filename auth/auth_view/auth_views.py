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

    # supported authentication methods
    methods = ["OIDC", "CAS"]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        # get enabled auth methods based on priority
        self.auth_methods = AuthMethod.objects.filter(
            enabled=True,
            priority__gte=0,
            name__in=self.methods
        )

        # get enabled auth configs for the above auth methods
        self.auth_configs = AuthConfig.objects.filter(
            enabled=True,
            auth_method__in=self.auth_methods
        )

        # at this point auth_configs should only contain one config (because
        # multiple cannot be enabled)
        if len(self.auth_methods) == 1:
            self.current_auth_method = self.auth_methods[0]
            self.current_auth_config = self.auth_configs[0]
        elif len(self.auth_methods) == 0:
            self.logger.debug("No SSO authentication method enabled")
            return redirect("/")

    def get(self, request, *args, **kwargs):
        """
        Verify if CAS or OIDC is enabled and configured and build the redirect
        url.
        Also check the config for the AUTO_REDIRECT setting.
        """
        for supported_method in self.methods:
            if self.current_auth_config.auth_method.name == supported_method:
                # get redirect url
                login_view = LoginView()
                url_redirect = getattr(login_view,
                                       f"{supported_method.lower()}_login")(request)

        # check if AUTO_REDIRECT is enabled
        # TODO : additonal check to check for NO_AUTO=1
        if self.current_auth_config.config['AUTO_REDIRECT'] is True:
            return JsonResponse({'SSO': True, 'auto_redirect': True,
                                 'redirect_url': url_redirect})
        else:
            # OIDC/CAS is enabled but AUTO_REDIRECT is disabled
            # front will display the 'SSO Login' button and we specify the url
            # to use for the redirect
            return JsonResponse({'SSO': True, 'auto_redirect': False,
                                 'redirect_url': url_redirect})


class LoginView(BaseAuthView):
    """
    View to handle login requests.
    """
    def cas_login(self, request):
        """Redirect to CAS login page"""
        cas_login_url = (self.current_auth_config.config['SERVER_URL'] +
                         self.current_auth_config.config['LOGIN_ROUTE'])
        service_url = request.build_absolute_uri(reverse('callback'))

        redirect_url = cas_login_url + '?service=' + service_url

        return redirect_url

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

        return redirect_url


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
