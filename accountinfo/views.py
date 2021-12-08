from permission.permissions import DefaultModelPermissions
from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.serializers import AccountinfoConfigSerializer, \
    AccountinfoDataSerializer, \
    AccountinfoValueSerializer
from rest_framework import viewsets


class AccountinfoConfigViewSet(viewsets.ModelViewSet):
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


class AccountinfoValueViewSet(viewsets.ModelViewSet):
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


class AccountinfoDataViewSet(viewsets.ModelViewSet):
    """
    This class will define the view behavior

    Args:
        viewsets ([OCSVIewSet])
    """

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = AccountinfoData.objects.all()
    serializer_class = AccountinfoDataSerializer
    model = AccountinfoData
