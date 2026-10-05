from rest_framework import permissions


class HasDebugMode(permissions.BasePermission):
    """
    Access to the debug endpoints. DefaultModelPermissions can not be used:
    a POST would require debug.add_debugmode, which does not exist.
    """

    def has_permission(self, request, view):
        return request.user.has_perm("debug.view_debugmode")
