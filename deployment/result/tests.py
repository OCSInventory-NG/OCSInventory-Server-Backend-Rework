import pytest
from asset.asset_group.models import AssetGroup
from deployment.result.models import Result


def _row(**kwargs):
    return {"name": "pkg", "status": 1, "group": None, **kwargs}


@pytest.fixture
def mixed(admin_user, scope_setup):
    group = AssetGroup.objects.create(
        name="Mixed", user=admin_user, visibility="public"
    )
    group.assets.set([scope_setup.visible, scope_setup.hidden])
    return group


@pytest.fixture
def scoped(make_scoped_user, client_for, scope_setup):
    user = make_scoped_user(
        "add_result",
        "change_result",
        "view_result",
        asset_groups=[scope_setup.paris],
    )
    return client_for(user)


@pytest.mark.django_db
class TestResultScope:
    def test_post_visible_asset_is_accepted(self, scoped, scope_setup):
        response = scoped.post(
            "/deployment/results/", [_row(asset=scope_setup.visible.id)], format="json"
        )
        assert response.status_code == 201

    def test_post_hidden_asset_is_refused(self, scoped, scope_setup):
        response = scoped.post(
            "/deployment/results/", [_row(asset=scope_setup.hidden.id)], format="json"
        )
        assert response.status_code == 400
        assert "Unknown asset." in response.data["error"]
        assert not Result.objects.exists()

    def test_post_group_with_hidden_asset_is_refused(self, scoped, scope_setup, mixed):
        response = scoped.post(
            "/deployment/results/",
            [_row(asset=scope_setup.visible.id, group=mixed.id)],
            format="json",
        )
        assert response.status_code == 400
        assert (
            "Asset group contains assets outside your scope." in response.data["error"]
        )

    def test_post_group_inside_scope_is_accepted(self, scoped, scope_setup):
        response = scoped.post(
            "/deployment/results/",
            [_row(asset=scope_setup.visible.id, group=scope_setup.paris.id)],
            format="json",
        )
        assert response.status_code == 201

    def test_patch_to_hidden_asset_is_refused(self, scoped, scope_setup):
        result = Result.objects.create(asset=scope_setup.visible, name="pkg")
        response = scoped.patch(
            f"/deployment/results/{result.id}/",
            {"asset": scope_setup.hidden.id},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["asset"] == ["Unknown asset."]

    def test_unscoped_post_accepts_any_asset(self, api_client, scope_setup):
        response = api_client.post(
            "/deployment/results/", [_row(asset=scope_setup.hidden.id)], format="json"
        )
        assert response.status_code == 201
