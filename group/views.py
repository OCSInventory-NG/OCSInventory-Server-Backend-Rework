from django.contrib.auth.models import Group, Permission
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from group.serializers import GroupSerializer


class GroupViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [IsAuthenticated]

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
