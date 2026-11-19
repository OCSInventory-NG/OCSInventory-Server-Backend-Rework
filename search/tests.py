import pytest
from inventory.software.models import SoftwareDictionary
from search.views import SearchView

LINUX = {
    "object": "InventoryBase",
    "field": "osname",
    "operator": "icontains",
    "value": "Linux",
    "link": "AND",
}

FIREFOX = {
    "object": "software_dictionary_entries",
    "field": "name",
    "operator": "iexact",
    "value": "firefox",
    "link": "AND",
}


def _name(value, link="AND"):
    return {
        "object": "InventoryBase",
        "field": "name",
        "operator": "iexact",
        "value": value,
        "link": link,
    }


@pytest.mark.django_db
class TestSearchScope:
    @pytest.fixture
    def scoped(self, scope_setup, make_scoped_user, client_for):
        user = make_scoped_user("view_inventorybase", asset_groups=[scope_setup.paris])
        return client_for(user)

    @pytest.fixture
    def plain(self, make_scoped_user, client_for):
        user = make_scoped_user("view_inventorybase", username="plain")
        return client_for(user)

    @pytest.fixture
    def firefox(self, scope_setup):
        entry = SoftwareDictionary.objects.create(name="firefox", installation_number=2)
        entry.assets.set([scope_setup.visible, scope_setup.hidden])
        return entry

    def test_search_returns_scope_assets_only(self, scoped, scope_setup):
        response = scoped.post("/search/", {"search_data": [[LINUX]]}, format="json")
        assert [a["id"] for a in response.data] == [scope_setup.visible.id]

    def test_ungrouped_search_returns_scope_assets_only(self, scoped, scope_setup):
        data = {"search_data": [[LINUX]], "ungroup": True}
        response = scoped.post("/search/", data, format="json")
        assert {row["id"] for row in response.data} == {scope_setup.visible.id}

    def test_or_groups_stay_in_scope(self, scoped, scope_setup):
        data = {"search_data": [[_name("visible")], [_name("hidden", link="OR")]]}
        response = scoped.post("/search/", data, format="json")
        assert [a["id"] for a in response.data] == [scope_setup.visible.id]

    def test_process_search_without_request_is_not_scoped(self, scope_setup):
        # the DynaGroups task path
        ids = set(SearchView().process_search([[LINUX]]).values_list("id", flat=True))
        assert ids == {scope_setup.visible.id, scope_setup.hidden.id}

    @pytest.mark.parametrize("ungroup", [False, True])
    def test_software_match_hides_stored_count(
        self, scoped, scope_setup, firefox, ungroup
    ):
        data = {"search_data": [[FIREFOX]], "ungroup": ungroup}
        response = scoped.post("/search/", data, format="json")
        assert [row["id"] for row in response.data] == [scope_setup.visible.id]
        match = response.data[0]["matched"]["software_dictionary_entries"][0]
        assert match["name"] == "firefox"
        assert "installation_number" not in match

    @pytest.mark.parametrize("ungroup", [False, True])
    def test_unscoped_software_match_keeps_stored_count(self, plain, firefox, ungroup):
        data = {"search_data": [[FIREFOX]], "ungroup": ungroup}
        response = plain.post("/search/", data, format="json")
        assert [
            row["matched"]["software_dictionary_entries"][0]["installation_number"]
            for row in response.data
        ] == [2, 2]
