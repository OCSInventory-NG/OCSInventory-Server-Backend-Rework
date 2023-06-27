from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.serializers import (
    AccountinfoConfigSerializer,
    AccountinfoDataSerializer,
    AccountinfoValueSerializer,
)
from permission.permissions import DefaultModelPermissions
from ocsinventory_backend.ocs_framework import viewsets


class AccountinfoConfigViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = AccountinfoConfig.objects.all()
    serializer_class = AccountinfoConfigSerializer
    model = AccountinfoConfig


class AccountinfoValueViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = AccountinfoValue.objects.all()
    serializer_class = AccountinfoValueSerializer
    model = AccountinfoValue


class AccountinfoDataViewSet(viewsets.OCSViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """
    # filters
    filterset_fields = ['object_slug', 'object_id']

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = AccountinfoData.objects.all()
    serializer_class = AccountinfoDataSerializer
    model = AccountinfoData
