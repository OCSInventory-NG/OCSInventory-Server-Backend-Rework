from django.contrib.auth.models import Permission
from django.urls import Resolver404, resolve
from permission.permissions import DefaultModelPermissions
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import (
    AllowAny,
    DjangoModelPermissions,
    IsAuthenticated,
)
from rest_framework.views import APIView


def resolve_calls(calls):
    """
    Give the permissions required by each API call. Nothing is executed: the
    answer comes from the urlconf and the DRF permission classes, so it is what
    the backend actually checks.
    """
    return {
        "calls": [_resolve_call(call["method"].upper(), call["path"]) for call in calls]
    }


def _resolve_call(method, path):
    path = path.split("?")[0].lstrip("/")
    entry = {
        "method": method,
        "path": path,
        "operation": "",
        "access": "error",
        "permissions": [],
        "detail": "",
    }

    try:
        match = resolve(f"/{path}")
    except Resolver404:
        entry["detail"] = "unknown_endpoint"
        return entry

    view_class = getattr(match.func, "cls", None)
    if view_class is None or not issubclass(view_class, APIView):
        entry["detail"] = "not_api_endpoint"
        return entry

    handler = _handler_name(match, view_class, method)
    if handler is None:
        entry["detail"] = "method_not_allowed"
        return entry

    entry["operation"] = handler
    entry.update(_describe_access(view_class, handler, method))
    return entry


def _handler_name(match, view_class, method):
    if method.lower() not in view_class.http_method_names:
        return None
    if method == "OPTIONS":
        return "metadata"

    actions = getattr(match.func, "actions", None)
    lookup = "get" if method == "HEAD" else method.lower()
    if actions is None:
        return method.lower() if hasattr(view_class, lookup) else None
    return actions.get(lookup)


def _describe_access(view_class, handler, method):
    handler_function = getattr(view_class, handler, None)
    action_kwargs = getattr(handler_function, "kwargs", {}) or {}
    permission_classes = action_kwargs.get(
        "permission_classes", view_class.permission_classes
    )

    permissions = []
    custom = []
    authenticated = False

    for permission_class in permission_classes:
        if issubclass(permission_class, AllowAny):
            continue
        if (
            issubclass(permission_class, DefaultModelPermissions)
            and method == "OPTIONS"
        ):
            # DefaultModelPermissions lets any authenticated user read the
            # OPTIONS metadata, see permission/permissions.py
            authenticated = True
        elif issubclass(permission_class, DjangoModelPermissions):
            required = _model_permissions(permission_class, view_class, method)
            if required is None:
                custom.append(permission_class.__name__)
            else:
                authenticated = True
                permissions += required
        elif issubclass(permission_class, IsAuthenticated):
            authenticated = True
        else:
            custom.append(permission_class.__name__)

    detail = ""
    if custom:
        access = "custom"
        detail = ", ".join(custom)
    elif permissions:
        access = "permissions"
    elif authenticated:
        access = "authenticated"
    else:
        access = "public"

    return {
        "access": access,
        "permissions": [_permission_entry(permission) for permission in permissions],
        "detail": detail,
    }


def _model_permissions(permission_class, view_class, method):
    queryset = getattr(view_class, "queryset", None)
    if queryset is None:
        return None
    try:
        return permission_class().get_required_permissions(method, queryset.model)
    except MethodNotAllowed:
        return None


def _permission_entry(permission):
    app_label, codename = permission.split(".", 1)
    instance = Permission.objects.filter(
        content_type__app_label=app_label, codename=codename
    ).first()
    return {"codename": permission, "name": instance.name if instance else ""}
