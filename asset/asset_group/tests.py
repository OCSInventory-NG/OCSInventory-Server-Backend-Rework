import pytest
from asset.asset_group.models import AssetGroup
from deployment.result.models import Result
from django.contrib.auth.models import Group, Permission, User
from group.models import GroupAssetScope
from rest_framework.test import APIClient


def _user_with_full_assetgroup_permissions(username):
    user = User.objects.create_user(username=username, password="password")
    user.user_permissions.set(
        Permission.objects.filter(codename__endswith="_assetgroup")
    )
    return user


@pytest.fixture
def owner(db):
    return _user_with_full_assetgroup_permissions("owner")


@pytest.fixture
def other_user(db):
    return _user_with_full_assetgroup_permissions("other")


def make_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestAssetGroupVisibility:
    def test_owner_sees_own_private_group(self, admin_user):
        AssetGroup.objects.create(
            name="My group", user=admin_user, visibility="private_personal"
        )

        client = make_client(admin_user)
        response = client.get("/asset/groups/")

        assert response.status_code == 200
        names = [group["name"] for group in response.data]
        assert "My group" in names

    def test_other_user_does_not_see_private_group(self, owner, other_user):
        AssetGroup.objects.create(
            name="Private group", user=owner, visibility="private_personal"
        )

        client = make_client(other_user)
        response = client.get("/asset/groups/")

        names = [group["name"] for group in response.data]
        assert "Private group" not in names

    def test_other_user_sees_public_group(self, owner, other_user):
        AssetGroup.objects.create(name="Public group", user=owner, visibility="public")

        client = make_client(other_user)
        response = client.get("/asset/groups/")

        names = [group["name"] for group in response.data]
        assert "Public group" in names

    def test_list_requires_authentication(self):
        response = APIClient().get("/asset/groups/")

        assert response.status_code == 401


@pytest.mark.django_db
class TestAssetGroupUpdate:
    def test_owner_can_update_own_group(self, owner):
        group = AssetGroup.objects.create(
            name="My group", user=owner, visibility="private_personal"
        )
        client = make_client(owner)

        response = client.patch(
            f"/asset/groups/{group.id}/", {"name": "Renamed"}, format="json"
        )

        assert response.status_code == 200
        group.refresh_from_db()
        assert group.name == "Renamed"

    def test_other_user_cannot_update_private_group(self, owner, other_user):
        group = AssetGroup.objects.create(
            name="My group", user=owner, visibility="private_personal"
        )
        client = make_client(other_user)

        response = client.patch(
            f"/asset/groups/{group.id}/", {"name": "Renamed"}, format="json"
        )

        # a private group is invisible to them, it is not even found
        assert response.status_code == 404
        group.refresh_from_db()
        assert group.name == "My group"

    def test_other_user_cannot_update_public_group_they_do_not_own(
        self, owner, other_user
    ):
        group = AssetGroup.objects.create(
            name="Public group", user=owner, visibility="public"
        )
        client = make_client(other_user)

        response = client.patch(
            f"/asset/groups/{group.id}/", {"name": "Renamed"}, format="json"
        )

        assert response.status_code == 403


@pytest.mark.django_db
class TestAssetGroupDelete:
    def test_owner_can_delete_own_group(self, owner):
        group = AssetGroup.objects.create(
            name="My group", user=owner, visibility="private_personal"
        )
        client = make_client(owner)

        response = client.delete(f"/asset/groups/{group.id}/")

        assert response.status_code == 204
        assert not AssetGroup.objects.filter(id=group.id).exists()

    def test_other_user_cannot_delete_group_they_do_not_own(self, owner, other_user):
        group = AssetGroup.objects.create(
            name="My group", user=owner, visibility="private_personal"
        )
        client = make_client(other_user)

        response = client.delete(f"/asset/groups/{group.id}/")

        # a private group is invisible to them, it is not even found
        assert response.status_code == 404
        assert AssetGroup.objects.filter(id=group.id).exists()


@pytest.mark.django_db
class TestAssetGroupCreate:
    def test_create_requires_add_permission(self, make_api_client):
        client = make_api_client("view_assetgroup")

        response = client.post(
            "/asset/groups/",
            {"name": "New group", "visibility": "private_personal"},
            format="json",
        )

        assert response.status_code == 403
        assert not AssetGroup.objects.filter(name="New group").exists()


@pytest.fixture
def mixed(admin_user, scope_setup):
    group = AssetGroup.objects.create(
        name="Mixed", user=admin_user, visibility="public"
    )
    group.assets.set([scope_setup.visible, scope_setup.hidden])
    return group


@pytest.fixture
def scoped_user(make_scoped_user, scope_setup):
    return make_scoped_user(
        "view_assetgroup",
        "add_assetgroup",
        "change_assetgroup",
        "view_result",
        asset_groups=[scope_setup.paris],
    )


@pytest.fixture
def scoped(client_for, scoped_user):
    return client_for(scoped_user)


@pytest.fixture
def mine(scoped_user, scope_setup):
    group = AssetGroup.objects.create(
        name="Mine", user=scoped_user, visibility="public"
    )
    group.assets.set([scope_setup.visible])
    return group


@pytest.mark.django_db
class TestAssetGroupScope:
    def test_group_detail_lists_visible_assets_only(self, scoped, mixed, scope_setup):
        data = scoped.get(f"/asset/groups/{mixed.id}/").data
        assert data["assets"] == [scope_setup.visible.id]

    def test_expanded_assets_are_filtered(self, scoped, mixed, scope_setup):
        data = scoped.get(f"/asset/groups/{mixed.id}/?expand=assets").data
        assert [a["id"] for a in data["assets"]] == [scope_setup.visible.id]

    def test_result_expanding_group_filters_its_assets(
        self, scoped, mixed, scope_setup
    ):
        Result.objects.create(asset=scope_setup.visible, group=mixed, name="pkg")
        data = scoped.get("/deployment/results/?expand=group").data
        assert data[0]["group"]["assets"] == [scope_setup.visible.id]

    def test_post_with_hidden_asset_is_refused(self, scoped, scoped_user, scope_setup):
        response = scoped.post(
            "/asset/groups/",
            {
                "name": "New",
                "visibility": "public",
                "user": scoped_user.id,
                "assets": [scope_setup.hidden.id],
            },
            format="json",
        )
        assert response.status_code == 400
        assert "Unknown asset." in response.data["error"]

    def test_patch_with_hidden_asset_is_refused(self, scoped, mine, scope_setup):
        response = scoped.patch(
            f"/asset/groups/{mine.id}/",
            {"assets": [scope_setup.visible.id, scope_setup.hidden.id]},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["assets"] == ["Unknown asset."]

    def test_patch_keeps_hidden_assets(self, scoped, mine, scope_setup):
        mine.assets.set([scope_setup.visible, scope_setup.hidden])
        response = scoped.patch(
            f"/asset/groups/{mine.id}/",
            {"assets": [scope_setup.visible.id]},
            format="json",
        )
        assert response.status_code == 200
        assert set(mine.assets.values_list("id", flat=True)) == {
            scope_setup.visible.id,
            scope_setup.hidden.id,
        }

    def test_unscoped_patch_replaces_assets(self, api_client, mixed, scope_setup):
        api_client.patch(
            f"/asset/groups/{mixed.id}/",
            {"assets": [scope_setup.visible.id]},
            format="json",
        )
        assert set(mixed.assets.values_list("id", flat=True)) == {
            scope_setup.visible.id
        }


@pytest.mark.django_db
class TestAssetGroupScopeConstraints:
    @pytest.fixture(autouse=True)
    def paris_scope(self, scope_setup):
        group = Group.objects.create(name="paris-team")
        scope = GroupAssetScope.objects.create(group=group)
        scope.asset_groups.set([scope_setup.paris])

    @pytest.fixture
    def other(self, admin_user):
        return AssetGroup.objects.create(
            name="Other", user=admin_user, visibility="public"
        )

    def test_delete_scope_group_is_refused(self, api_client, scope_setup):
        response = api_client.delete(f"/asset/groups/{scope_setup.paris.id}/")
        assert response.status_code == 409
        message = "This asset group is used as a user group scope."
        assert response.data["detail"] == message
        assert AssetGroup.objects.filter(id=scope_setup.paris.id).exists()

    def test_bulk_delete_with_scope_group_is_refused(
        self, api_client, scope_setup, other
    ):
        response = api_client.post(
            "/asset/groups/?delete=1",
            {"ids": [scope_setup.paris.id, other.id]},
            format="json",
        )
        assert response.status_code == 409
        ids = [scope_setup.paris.id, other.id]
        assert AssetGroup.objects.filter(id__in=ids).count() == 2

    def test_delete_unused_group_works(self, api_client, other):
        assert api_client.delete(f"/asset/groups/{other.id}/").status_code == 204

    def test_scope_group_must_stay_public(self, api_client, scope_setup):
        response = api_client.patch(
            f"/asset/groups/{scope_setup.paris.id}/",
            {"visibility": "private_personal"},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["visibility"] == [
            "This asset group is used as a user group scope and must stay public."
        ]

    def test_unused_group_can_go_private(self, api_client, other):
        response = api_client.patch(
            f"/asset/groups/{other.id}/",
            {"visibility": "private_personal"},
            format="json",
        )
        assert response.status_code == 200
