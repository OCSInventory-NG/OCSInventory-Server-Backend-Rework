from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.serializers import (
    AccountinfoConfigSerializer,
    AccountinfoDataSerializer,
    AccountinfoValueSerializer,
)
from django.contrib.contenttypes.models import ContentType
from ocsinventory_backend.ocs_framework import viewsets
from permission.permissions import DefaultModelPermissions


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
    filterset_fields = ["object_slug", "object_id"]

    # Need to have permissions to consult
    permission_classes = [DefaultModelPermissions]

    queryset = AccountinfoData.objects.all()
    serializer_class = AccountinfoDataSerializer
    model = AccountinfoData

    @classmethod
    def generate_accountinfo(cls, obj, object_slug):
        """
        Creates AccountinfoData entries for an object if they don't exist

        Args:
            obj: The object to create account info for
            object_slug: The object type slug (e.g. 'inventory_base.inventorybase')
        """
        app, model = object_slug.split(".")
        content_type = ContentType.objects.get_by_natural_key(
            app_label=app, model=model
        )

        # existing entry?
        existing_data = AccountinfoData.objects.filter(
            content_type=content_type, object_id=obj.id
        ).first()

        if not existing_data:
            # getting all accountinfo configs for this target
            configs = AccountinfoConfig.objects.prefetch_related(
                "accountinfo_values"
            ).filter(datatarget="ASSET")

            if configs.exists():
                # accountdata structure
                accountdata = {}
                for config in configs:
                    if config.datatype == "CHECKBOX":
                        # empty list for checkboxes
                        accountdata[str(config.id)] = []
                    elif config.datatype == "SELECT":
                        # null value for select fields
                        accountdata[str(config.id)] = None
                    # TEXT or TEXTAREA
                    else:
                        accountdata[str(config.id)] = ""

                AccountinfoData.objects.create(
                    content_type=content_type,
                    object_id=obj.id,
                    object_slug=object_slug,
                    accountdata=accountdata,
                )
