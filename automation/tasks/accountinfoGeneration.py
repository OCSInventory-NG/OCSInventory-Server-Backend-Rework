from accountinfo.views import AccountinfoDataViewSet
from asset.inventory_base.models import InventoryBase
from automation.tasks.abstractTask import AbstractTask
from config.models import Config


class AccountInfoGeneration(AbstractTask):
    """
    Task to create missing AccountinfoData entries for assets. This task
    is intended to be run using the automation/scheduler module.
    """

    def execute(self):
        """
        Find all assets without AccountinfoData and create entries for them
        """
        if self.config_check():
            assets = self.get_assets()
            self.generate_accountinfo(assets)

    def config_check(self):
        """
        Check if accountinfo generation is set to automation mode
        """
        server_conf = Config.objects.filter(name="server").first()
        for item in server_conf.value:
            if item["name"] == "accountinfo_generation":
                return item["value"] == "automation"
        return False

    def get_assets(self):
        """
        Get all assets that need accountinfo generation
        """
        return InventoryBase.objects.all()

    def generate_accountinfo(self, assets):
        """
        Generate accountinfo for the given assets
        """
        try:
            for asset in assets:
                AccountinfoDataViewSet.generate_accountinfo(
                    asset, "inventory_base.inventorybase"
                )
        except Exception as e:
            print(f"Error generating accountinfo: {e}")
