import pytest
from asset.asset_group.models import AssetGroup
from django.contrib.auth.models import Group
from group.models import GroupAssetScope
from mgmt.management.commands.migrate import Command as MigrateCommand


@pytest.mark.django_db
def test_snmp_scanner_group_gets_scanner_permissions():
    MigrateCommand().assign_group_permissions()

    group = Group.objects.get(name="SnmpScanner")
    codenames = set(group.permissions.values_list("codename", flat=True))

    assert group.protection.is_protected
    assert codenames == {
        "view_config",
        "view_snmpconfig",
        "view_snmpscanner",
        "add_snmpscanner",
        "change_snmpscanner",
        "add_inventorybase",
        "change_inventorybase",
        "view_inventorybase",
        "view_template",
        "add_log",
    }


def _scoped_group(name, asset_groups):
    group = Group.objects.create(name=name)
    GroupAssetScope.objects.create(group=group).asset_groups.set(asset_groups)
    return group


@pytest.mark.django_db
class TestGroupAssetScopeApi:
    def test_group_without_scope_reads_null(self, api_client):
        group = Group.objects.create(name="helpdesk")
        assert api_client.get(f"/groups/{group.id}/").data["asset_groups"] is None

    def test_expand_lists_asset_group_names(
        self, api_client, scope_setup, admin_user
    ):
        lyon = AssetGroup.objects.create(
            name="Lyon", user=admin_user, visibility="public"
        )
        group = _scoped_group("helpdesk", [scope_setup.paris, lyon])
        data = api_client.get(f"/groups/{group.id}/?expand=asset_groups").data
        assert data["asset_groups"] == [
            {"id": lyon.id, "name": "Lyon"},
            {"id": scope_setup.paris.id, "name": "Paris"},
        ]
        listed = api_client.get("/groups/?expand=asset_groups").data
        assert next(g for g in listed if g["id"] == group.id) == data

    def test_patch_sets_scope(self, api_client, scope_setup):
        group = Group.objects.create(name="helpdesk")
        response = api_client.patch(
            f"/groups/{group.id}/",
            {"asset_groups": [scope_setup.paris.id]},
            format="json",
        )
        assert response.status_code == 200
        assert api_client.get(f"/groups/{group.id}/").data["asset_groups"] == [
            scope_setup.paris.id
        ]

    def test_patch_null_removes_scope(self, api_client, scope_setup):
        group = _scoped_group("helpdesk", [scope_setup.paris])
        response = api_client.patch(
            f"/groups/{group.id}/", {"asset_groups": None}, format="json"
        )
        assert response.status_code == 200
        assert not GroupAssetScope.objects.filter(group=group).exists()

    def test_patch_empty_list_restricts_to_nothing(self, api_client, scope_setup):
        group = _scoped_group("helpdesk", [scope_setup.paris])
        api_client.patch(f"/groups/{group.id}/", {"asset_groups": []}, format="json")
        assert GroupAssetScope.objects.filter(group=group).exists()
        assert api_client.get(f"/groups/{group.id}/").data["asset_groups"] == []

    def test_patch_without_field_keeps_scope(self, api_client, scope_setup):
        group = _scoped_group("helpdesk", [scope_setup.paris])
        api_client.patch(f"/groups/{group.id}/", {"name": "renamed"}, format="json")
        assert api_client.get(f"/groups/{group.id}/").data["asset_groups"] == [
            scope_setup.paris.id
        ]

    def test_non_public_asset_group_is_refused(self, api_client, admin_user):
        mine = AssetGroup.objects.create(
            name="Mine", user=admin_user, visibility="private_personal"
        )
        group = Group.objects.create(name="helpdesk")
        response = api_client.patch(
            f"/groups/{group.id}/", {"asset_groups": [mine.id]}, format="json"
        )
        assert response.status_code == 400
        assert response.data["asset_groups"] == [
            "Only public asset groups can be used as a scope."
        ]

    def test_post_copies_scope(self, api_client, scope_setup):
        response = api_client.post(
            "/groups/",
            {"name": "copy", "permissions": [], "asset_groups": [scope_setup.paris.id]},
            format="json",
        )
        assert response.status_code == 201
        scope = Group.objects.get(name="copy").asset_scope
        assert list(scope.asset_groups.values_list("id", flat=True)) == [
            scope_setup.paris.id
        ]

    def test_post_empty_list_restricts_to_nothing(self, api_client):
        api_client.post(
            "/groups/",
            {"name": "copy", "permissions": [], "asset_groups": []},
            format="json",
        )
        assert not Group.objects.get(name="copy").asset_scope.asset_groups.exists()

    def test_patch_response_reflects_new_scope(self, api_client, scope_setup):
        group = _scoped_group("helpdesk", [scope_setup.paris])
        none = api_client.patch(
            f"/groups/{group.id}/", {"asset_groups": None}, format="json"
        )
        assert none.data["asset_groups"] is None
        empty = api_client.patch(
            f"/groups/{group.id}/", {"asset_groups": []}, format="json"
        )
        assert empty.data["asset_groups"] == []
