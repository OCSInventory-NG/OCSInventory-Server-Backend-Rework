import logging
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from auth.auth_backend.cas_backend import CustomCASBackend
from auth.auth_backend.oidc_backend import CustomOIDCBackend
from auth.auth_config.models import AuthConfig
from auth.auth_method.models import AuthMethod
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.signals import user_logged_in
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views import View
from rest_framework.authtoken.models import Token


class BaseAuthView(View):
    """
    Base view for authentication, to be inherited by LoginView and CallbackView.
    Retrieves enabled auth methods, configs and mappings.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.current_auth_config = None
        self.current_auth_method = None
        # get enabled auth methods based on priority
        self.auth_methods = AuthMethod.objects.filter(enabled=True, auth_type="SSO")

        # get enabled auth configs for the above auth methods
        self.auth_configs = AuthConfig.objects.filter(
            enabled=True, auth_method__in=self.auth_methods
        )

        # at this point auth_configs should only contain one config (because
        # multiple cannot be enabled)
        if len(self.auth_methods) == 1:
            self.current_auth_method = self.auth_methods[0]
            if len(self.auth_configs) == 1:
                self.current_auth_config = self.auth_configs[0]
            elif len(self.auth_configs) == 0:
                self.logger.debug(
                    "No enabled configuration found for SSO configuration"
                )

        elif len(self.auth_methods) == 0:
            self.logger.debug("No SSO authentication method enabled")

    def _build_frontend_redirect(self, token=None):
        frontend_redirect = settings.FRONTEND_REDIRECT
        if not frontend_redirect:
            return None
        parts = urlsplit(frontend_redirect)
        fragment = parts.fragment
        if token:
            fragment_params = dict(parse_qsl(fragment, keep_blank_values=True))
            fragment_params["token_authentication"] = token
            fragment = urlencode(fragment_params)
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, parts.query, fragment)
        )

    def get(self, request, *args, **kwargs):
        """
        Verify if CAS or OIDC is enabled and configured and build the redirect
        url.
        Also check the config for the AUTO_REDIRECT setting.
        """
        # if no SSO config is enabled or set
        if not self.current_auth_config or not self.current_auth_method:
            self.logger.debug("No enabled configuration found for SSO configuration")
            response = {"SSO": False, "auto_redirect": False}
            return JsonResponse(response)

        # get redirect url
        login_view = LoginView()
        url_redirect = getattr(
            login_view, f"{self.current_auth_config.auth_method.name.lower()}_login"
        )(request)

        response = {"SSO": True, "auto_redirect": True, "redirect_url": url_redirect}

        if self.current_auth_method.name == "OIDC":
            response["endpoint_logout"] = self.current_auth_config.config.get(
                "LOGOUT_ENDPOINT"
            )

        # AUTO_REDIRECT is not enabled
        if self.current_auth_config.config["AUTO_REDIRECT"] == 0:
            response["auto_redirect"] = False

        return JsonResponse(response)


class LoginView(BaseAuthView):
    """
    View to handle login requests.
    """

    def cas_login(self, request):
        """Redirect to CAS login page"""
        cas_login_url = (
            self.current_auth_config.config["SERVER_URL"]
            + self.current_auth_config.config["LOGIN_ROUTE"]
        )
        service_url = request.build_absolute_uri(reverse("callback"))
        redirect_url = cas_login_url + "?service=" + service_url

        return redirect_url

    def oidc_login(self, request):
        """Redirect to OIDC login page"""
        redirect_uri = request.build_absolute_uri(reverse("callback"))
        params = {
            "response_type": "code",
            "client_id": self.current_auth_config.config["CLIENT_ID"],
            "state": None,
            "scope": self.current_auth_config.config["SCOPES"],
            "redirect_uri": redirect_uri,
        }
        query = urlencode(params, quote_via=quote)

        redirect_url = "{url}?{query}".format(
            url=self.current_auth_config.config["AUTHORIZATION_ENDPOINT"], query=query
        )

        return redirect_url


class CallbackView(BaseAuthView):
    """
    View to handle callback requests.
    """

    def get(self, request, *args, **kwargs):
        """Handle callback requests from CAS or OIDC"""
        ticket = request.GET.get("ticket")
        if ticket:
            return self.cas_callback(request)

        code = request.GET.get("code")
        if code:
            return self.oidc_callback(request)

    def cas_callback(self, request):
        """Handle CAS callback requests"""
        ticket = request.GET.get("ticket")
        service_url = request.build_absolute_uri()
        # pass the ticket to CustomCASBackend
        customCASBackend = CustomCASBackend()
        user = customCASBackend.authenticate(request, ticket, service_url)

        if user is not None:
            login(request, user)
            request.session["auth_method"] = "sso"
            # Generate a token for the user
            token, created = Token.objects.get_or_create(user=user)
            # sending the user_logged_in signal manually
            user_logged_in.send(sender=user.__class__, request=request, user=user)
            # Include the token in the response
            redirect_url = self._build_frontend_redirect(token.key)
            if redirect_url:
                return HttpResponseRedirect(redirect_url)
            return JsonResponse({"token_authentication": token.key})

        else:
            redirect_url = self._build_frontend_redirect()
            if redirect_url:
                return HttpResponseRedirect(redirect_url)
            return HttpResponseRedirect("/")

    def oidc_callback(self, request):
        """Handle OIDC callback requests"""
        customOIDCBackend = CustomOIDCBackend()
        user = None
        user = customOIDCBackend.authenticate(request)
        if user is not None:
            login(request, user)
            request.session["auth_method"] = "sso"
            # Generate a token for the user
            token, created = Token.objects.get_or_create(user=user)
            # sending the user_logged_in signal manually
            user_logged_in.send(sender=user.__class__, request=request, user=user)
            # Include the token in the response
            redirect_url = self._build_frontend_redirect(token.key)
            if redirect_url:
                return HttpResponseRedirect(redirect_url)
            return JsonResponse({"token_authentication": token.key})

        else:
            redirect_url = self._build_frontend_redirect()
            if redirect_url:
                return HttpResponseRedirect(redirect_url)
            return HttpResponseRedirect("/")


class LogoutView(BaseAuthView):
    """
    View to handle logout requests.
    """

    def get(self, request, *args, **kwargs):
        auth_method = request.GET.get("method")

        if request.user.is_authenticated:
            Token.objects.filter(user=request.user).delete()
        logout(request)

        if auth_method == "sso" and self.current_auth_config:
            slo_enabled = self.current_auth_config.config.get("SLO_ENABLED", False)
            endpoint = self.current_auth_config.config.get("LOGOUT_ENDPOINT")
            if slo_enabled and endpoint:
                return HttpResponseRedirect(endpoint)

        frontend_redirect = getattr(settings, "FRONTEND_REDIRECT", "")
        if frontend_redirect:
            return HttpResponseRedirect(
                f"{frontend_redirect.rstrip('/')}/login/?noauto"
            )
        return HttpResponseRedirect(reverse("login"))
