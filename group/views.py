from django.contrib.auth.models import Group
from rest_framework import viewsets
from rest_framework import status
from permission.permissions import DefaultModelPermissions
from rest_framework.response import Response
from group.serializers import GroupSerializer


class GroupViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
