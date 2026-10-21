import pytest
from dashboard.layout.models import DashboardLayout


def dashboard(owner, **kwargs):
    return DashboardLayout.objects.create(
        name=kwargs.pop("name", "My dashboard"), layout=[], user=owner, **kwargs
    )


@pytest.fixture
def other(make_api_client):
    return make_api_client(
        "view_dashboardlayout",
        "add_dashboardlayout",
        "change_dashboardlayout",
        "delete_dashboardlayout",
        username="other",
    )


@pytest.mark.django_db
class TestDashboardLayoutVisibility:
    def test_a_private_dashboard_is_not_listed_for_someone_else(
        self, admin_user, other
    ):
        dashboard(admin_user)

        names = [item["name"] for item in other.get("/dashboard/layout/").data]

        assert "My dashboard" not in names

    def test_a_private_dashboard_of_someone_else_is_not_found(self, admin_user, other):
        layout = dashboard(admin_user)
        url = f"/dashboard/layout/{layout.id}/"

        assert other.get(url).status_code == 404
        assert other.patch(url, {"name": "taken"}, format="json").status_code == 404
        assert other.delete(url).status_code == 404
        layout.refresh_from_db()
        assert layout.name == "My dashboard"

    def test_a_public_dashboard_is_read_but_not_changed_by_someone_else(
        self, admin_user, other
    ):
        layout = dashboard(admin_user, visibility="public")
        url = f"/dashboard/layout/{layout.id}/"

        assert other.get(url).status_code == 200
        assert other.patch(url, {"name": "taken"}, format="json").status_code == 403
        assert other.delete(url).status_code == 403

    def test_a_group_member_edits_when_the_author_allows_it(
        self, admin_user, other, django_user_model
    ):
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")
        django_user_model.objects.get(username="other").groups.add(group)
        layout = dashboard(
            admin_user, visibility="private_group", allow_group_modification=True
        )
        layout.groups.add(group)

        response = other.patch(
            f"/dashboard/layout/{layout.id}/", {"name": "Ours"}, format="json"
        )

        assert response.status_code == 200, response.data
        layout.refresh_from_db()
        assert layout.name == "Ours"

    def test_the_owner_still_manages_their_dashboard(self, api_client, admin_user):
        layout = dashboard(admin_user)
        url = f"/dashboard/layout/{layout.id}/"

        assert api_client.patch(url, {"name": "Mine"}, format="json").status_code == 200
        assert api_client.delete(url).status_code == 204


@pytest.mark.django_db
class TestDashboardLayoutOwner:
    def test_the_creator_owns_the_dashboard(self, other, django_user_model):
        response = other.post(
            "/dashboard/layout/", {"name": "Mine", "layout": []}, format="json"
        )

        assert response.status_code == 201, response.data
        owner = DashboardLayout.objects.get(name="Mine").user
        assert owner == django_user_model.objects.get(username="other")

    def test_the_payload_cannot_hand_the_dashboard_to_someone_else(
        self, other, admin_user, django_user_model
    ):
        response = other.post(
            "/dashboard/layout/",
            {"name": "Mine", "layout": [], "user": admin_user.id},
            format="json",
        )

        assert response.status_code == 201, response.data
        owner = DashboardLayout.objects.get(name="Mine").user
        assert owner == django_user_model.objects.get(username="other")

    def test_the_owner_cannot_be_changed_afterwards(
        self, api_client, admin_user, django_user_model
    ):
        someone = django_user_model.objects.create_user(username="someone")
        layout = dashboard(admin_user)

        api_client.patch(
            f"/dashboard/layout/{layout.id}/", {"user": someone.id}, format="json"
        )

        layout.refresh_from_db()
        assert layout.user == admin_user
