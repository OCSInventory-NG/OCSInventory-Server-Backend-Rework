from automation.tasks.abstractTask import AbstractTask
from asset.inventory_base.models import InventoryBase
from accountinfo.views import AccountinfoDataViewSet


class AccountInfoCreation(AbstractTask):
    """
    Task to create missing AccountinfoData entries for assets. This task
    is intended to be run using the automation/scheduler module.
    """

    def execute(self):
        """
        Find all assets without AccountinfoData and create entries for them
        """
        # for all assets
        assets = InventoryBase.objects.all()

        for asset in assets:
            AccountinfoDataViewSet.generate_accountinfo(asset, "inventory_base.inventorybase")
