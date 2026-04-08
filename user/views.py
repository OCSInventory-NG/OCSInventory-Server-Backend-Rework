from django.contrib.auth.models import User
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from user.serializers import (
    MyAccountSerializer,
    UserGroupAssignmentSerializer,
    UserSerializer,
)
from user.services import delete_group_assignment as delete_group_assignment_service
from user.services import (
    upsert_group_assignment,
)


class UserViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = User.objects.all().prefetch_related(
        "usergroupassignment_set__group",
        "usergroupassignment_set__source_content_type",
    )
    serializer_class = UserSerializer
    model = User

    @action(
        detail=True,
        methods=["post"],
        url_path="group-assignments",
    )
    def add_group_assignment(self, request, pk=None):
        """Create or update one user group assignment and resync effective groups"""
        user = self.get_object()
        serializer = UserGroupAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        group_id = serializer.validated_data["group_id"]
        source = serializer.validated_data["source"]
        source_content_type = serializer.validated_data["source_content_type"]
        source_object_id = serializer.validated_data.get("source_object_id")

        upsert_group_assignment(
            user=user,
            group_id=group_id,
            source=source,
            source_content_type=source_content_type,
            source_object_id=source_object_id,
        )
        user.refresh_from_db()

        return Response(
            {
                "groups": list(user.groups.values_list("id", flat=True)),
                "group_assignments": UserSerializer.build_group_assignments_payload(
                    user
                ),
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"group-assignments/(?P<assignment_id>[^/.]+)",
    )
    def delete_group_assignment(self, request, pk=None, assignment_id=None):
        """Delete one user group assignment and resync effective groups"""
        user = self.get_object()
        delete_group_assignment_service(user, assignment_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyAccountViewSet(viewsets.OCSViewSet):
    """This class will define the view behavior"""

    # Need to be authenticated to consult
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MyAccountSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        """Query set get only the current connected user"""
        return User.objects.filter(username=self.request.user)

    def list(self, request, *args, **kwargs):
        """Dedicated my account json response"""
        user = User.objects.filter(username=self.request.user).first()
        raw_permissions = user.get_all_permissions()
        refined_permissions = []
        refined_groups = []

        # Get the user groups
        for group in request.user.groups.all():
            refined_groups.append(group.id)

        # Remove the first part of the permission "object.permname"
        for permission in raw_permissions:
            splitted_permission = permission.split(".")
            refined_permissions.append(
                splitted_permission[0] + "_" + splitted_permission[1]
            )
            refined_permissions.sort()

        reponse = {
            "id": getattr(user, "id", ""),
            "username": getattr(user, "username", ""),
            "email": getattr(user, "email", ""),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
            "is_superuser": getattr(user, "is_superuser", False),
            "groups": refined_groups,
            "group_assignments": UserSerializer.build_group_assignments_payload(user),
            "full_permissions": refined_permissions,
        }
        return Response(reponse)
