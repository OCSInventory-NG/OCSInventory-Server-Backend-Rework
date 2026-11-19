import pytest
from inventory.software.models import SoftwareDictionary


@pytest.fixture
def scoped(make_scoped_user, client_for, scope_setup):
    user = make_scoped_user("view_softwaredictionary", asset_groups=[scope_setup.paris])
    return client_for(user)


@pytest.fixture
def plain(make_scoped_user, client_for):
    user = make_scoped_user("view_softwaredictionary", username="plain")
    return client_for(user)


@pytest.fixture
def second(scope_setup, make_asset):
    second = make_asset("second")
    scope_setup.paris.assets.add(second)
    return second


@pytest.fixture
def entries(scope_setup, second):
    # stored counts are set so that sorting on them gives another order
    firefox = SoftwareDictionary.objects.create(name="firefox", installation_number=2)
    firefox.assets.set([scope_setup.visible, scope_setup.hidden])
    curl = SoftwareDictionary.objects.create(name="curl", installation_number=1)
    curl.assets.set([scope_setup.visible, second])
    vim = SoftwareDictionary.objects.create(name="vim", installation_number=5)
    vim.assets.set([scope_setup.hidden])
    return firefox, curl, vim


@pytest.mark.django_db
class TestSoftwareDictionaryScope:
    def test_assets_and_count_follow_scope(self, scoped, scope_setup, second, entries):
        data = scoped.get("/software_dictionary/").data
        rows = {
            e["name"]: (sorted(e["assets"]), e["installation_number"]) for e in data
        }
        assert rows == {
            "firefox": ([scope_setup.visible.id], 1),
            "curl": (sorted([scope_setup.visible.id, second.id]), 2),
        }

    def test_software_outside_scope_is_hidden(self, scoped, entries):
        vim = entries[2]
        names = [e["name"] for e in scoped.get("/software_dictionary/").data]
        assert "vim" not in names
        assert scoped.get(f"/software_dictionary/{vim.id}/").status_code == 404

    def test_sort_uses_visible_count(self, scoped, entries):
        data = scoped.get("/software_dictionary/?ordering=-installation_number").data
        assert [e["name"] for e in data] == ["curl", "firefox"]

    def test_filter_uses_visible_count(self, scoped, entries):
        data = scoped.get("/software_dictionary/?installation_number=1").data
        assert [e["name"] for e in data] == ["firefox"]

    def test_unscoped_user_gets_stored_count(self, plain, scope_setup, entries):
        data = {e["name"]: e for e in plain.get("/software_dictionary/").data}
        assert data["firefox"]["installation_number"] == 2
        assert len(data["firefox"]["assets"]) == 2
        assert data["vim"]["installation_number"] == 5
