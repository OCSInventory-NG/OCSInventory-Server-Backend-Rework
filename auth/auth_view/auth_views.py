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
from auth.auth_mapping.models import AuthMapping


class AuthView(View):
    """
    Special view meant to be called without authentication to determine
    authentication methods and configuration.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # get all enabled auth methods in order of priority
        self.auth_methods = AuthMethod.objects.filter(
            enabled=True,
            priority__gte=0,
            name__in=["OIDC", "CAS"]
        ).order_by("priority")

        # get all enabled auth configs, grouped by auth method and ordered by priority
        self.auth_configs = AuthConfig.objects.filter(
            enabled=True,
            auth_method__enabled=True,
            auth_method__name__in=["OIDC", "CAS"]
        ).order_by("auth_method__priority", "priority")

        # get all enabled auth mappings, grouped by auth method
        self.auth_mappings = AuthMapping.objects.filter(
            auth_config__auth_method__enabled=True,
            auth_config__enabled=True,
            auth_config__auth_method__name__in=["OIDC", "CAS"]
        ).order_by("auth_config__auth_method__priority")

    def get(self, request, *args, **kwargs):
        """
        Determine the appropriate authentication method and redirect to the
        appropriate view.
        LDAP authentication is handled by the basic login form but CAS and OIDC
        will require redirection to the appropriate server.

        This function will only redirect to the CAS or OIDC server if the method
        is enabled and a configuration exists.
        If method is LDAP, it will redirect to the basic login form.
        """

        # need to handle both /login and the redirect to /callback

        # /login
        if request.path == "/login/":
            # check if either CAS or OIDC is enabled
            # these are already ordered by priority
            for auth_method in self.auth_methods:
                if auth_method.name == "CAS":
                    # call cas_login
                    casView = CASAuthView()
                    return casView.cas_login(request)
                elif auth_method.name == "OIDC":
                    # call oidc_login
                    oidcView = OIDCAuthView()
                    return oidcView.oidc_login(request)

            # TODO : redirect to basic login form
            return HttpResponseRedirect("/")

        # /callback (OIDC provider or CAS server redirect back to this url)
        elif request.path == "/callback/":
            # if request contains ticket, call cas_callback
            ticket = request.GET.get('ticket')
            if ticket:
                casView = CASAuthView()
                return casView.cas_callback(request)
            # if request contains code, call oidc_callback
            code = request.GET.get('code')
            if code:
                oidcView = OIDCAuthView()
                return oidcView.oidc_callback(request)


class CASAuthView(AuthView):
    """
    Special view to handle CAS authentication
    """

    def __init__(self):
        # get all CAS config from database
        self.configs = AuthConfig.objects.filter(auth_method__name="CAS",
                                                 enabled=True).order_by("priority")
        self.mappings = AuthMapping.objects.filter(
                                                auth_config__auth_method__name="CAS")

    def cas_login(self, request):
        # redirect the user to the CAS server
        # TODO : getting 1st for now but need to handle multiple (or prevent multiple)
        if len(self.configs) > 0:
            cas_config = self.configs[0]
        else:
            # no CAS config found, redirect to login page
            return redirect("/login")

        cas_login_url = (cas_config.config['SERVER_URL'] +
                         cas_config.config['LOGIN_ROUTE'])
        service_url = request.build_absolute_uri(reverse('callback'))

        return redirect(cas_login_url + '?service=' + service_url)

    def cas_callback(self, request):
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


class OIDCAuthView(AuthView):
    """
    Special view to handle OIDC authentication
    """

    def __init__(self):
        # get all OIDC config from database
        self.configs = AuthConfig.objects.filter(auth_method__name="OIDC",
                                                 enabled=True).order_by("priority")
        self.mappings = AuthMapping.objects.filter(
                                                 auth_config__auth_method__name="OIDC")

    def oidc_login(self, request):
        # redirect the user to the OIDC server
        # TODO : getting 1st for now but need to handle multiple (or prevent multiple)
        if len(self.configs) > 0:
            oidc_config = self.configs[0]
        else:
            # no OIDC config found, redirect to login page
            return redirect("/login")

        params = {
            "response_type": "code",
            "client_id": oidc_config.config['CLIENT_ID'],
            "redirect_uri": request.build_absolute_uri(reverse('callback')),
            "state": None,
            "scope": oidc_config.config['SCOPES'],
        }
        query = urlencode(params, quote_via=quote)

        redirect_url = "{url}?{query}".format(
            url=oidc_config.config['AUTHORIZATION_ENDPOINT'], query=query)
        return HttpResponseRedirect(redirect_url)

    def oidc_callback(self, request):
        # pass the ticket to CustomCASBackend
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
