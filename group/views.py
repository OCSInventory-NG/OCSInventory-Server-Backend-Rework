from django.contrib.auth.models import Group
from permission.permissions import DefaultModelPermissions
from group.serializers import GroupSerializer
from ocsinventory_backend.ocs_framework import viewsets


class GroupViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([ModelViewSet])
    """

    # Need to be authenticated to consult
    permission_classes = [DefaultModelPermissions]

    queryset = Group.objects.all()
    serializer_class = GroupSerializer
