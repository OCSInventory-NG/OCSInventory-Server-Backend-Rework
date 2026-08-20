import pytest
from asset.asset_group.models import AssetGroup
from django.contrib.auth.models import Permission, User
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
        AssetGroup.objects.create(name="My group", user=admin_user, visibility="private_personal")

        client = make_client(admin_user)
        response = client.get("/asset/groups/")

        assert response.status_code == 200
        names = [group["name"] for group in response.data]
        assert "My group" in names

    def test_other_user_does_not_see_private_group(self, owner, other_user):
        AssetGroup.objects.create(name="Private group", user=owner, visibility="private_personal")

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

        assert response.status_code == 403
        group.refresh_from_db()
        assert group.name == "My group"

    def test_other_user_cannot_update_public_group_they_do_not_own(
        self, owner, other_user
    ):
        group = AssetGroup.objects.create(name="Public group", user=owner, visibility="public")
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

        assert response.status_code == 403
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
