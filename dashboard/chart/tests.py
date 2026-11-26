import pytest


@pytest.fixture
def scoped(make_scoped_user, client_for, scope_setup):
    user = make_scoped_user("view_inventorybase", asset_groups=[scope_setup.paris])
    return client_for(user)


@pytest.fixture
def plain(make_scoped_user, client_for, scope_setup):
    user = make_scoped_user("view_inventorybase", username="plain")
    return client_for(user)


@pytest.mark.django_db
class TestDashboardChartScope:
    def test_total_counts_scope_only(self, scoped):
        response = scoped.get("/dashboard/chart/total_ALL/")
        assert response.data == {"total": 1, "contacted": 1}

    def test_os_count_scope_only(self, scoped):
        assert scoped.get("/dashboard/chart/oscount/").data["series"] == [1]

    def test_last_contacted_scope_only(self, scoped):
        response = scoped.get("/dashboard/chart/lastcontacted/")
        assert sum(response.data["series"][0]["data"]) == 1

    def test_unscoped_total_counts_everything(self, plain):
        assert plain.get("/dashboard/chart/total_ALL/").data["total"] == 2
