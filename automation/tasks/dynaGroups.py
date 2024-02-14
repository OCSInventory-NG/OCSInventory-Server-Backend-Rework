from automation.tasks.abstractTask import AbstractTask
from asset.asset_group.models import AssetGroup
from search.views import SearchView


class DynaGroups(AbstractTask):
    """
    DynaGroups class
    Automation tasks handling the re generation assets list for dynamic groups
    Runs the search query and updates the assets list
    """

    def execute(self):
        """
        - get all dynamic groups
        - for each group, get the search query
        - run the search query
        - update the assets list
        """
        dyna = self.get_dynamic_groups()
        for group in dyna:
            search = group.search
            assets = self.run_search_query(search)
            self.update_assets_list(group, assets)

    def get_dynamic_groups():
        """
        Get all dynamic groups
        """
        dyna = AssetGroup.objects.filter(is_dynamic=True)
        return dyna

    def run_search_query(search):
        """
        Run the search query
        """
        search_view = SearchView()
        assets = search_view.process_search(search)
        assets = assets.values_list('id', flat=True)
        return assets

    def update_assets_list(group, assets):
        """
        Update the assets list
        """
        try:
            group.assets.set(assets)
            group.save()
        except Exception as e:
            print(e)
