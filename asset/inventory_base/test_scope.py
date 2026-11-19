from types import SimpleNamespace

import pytest
from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from asset.inventory_base.scope import visible_asset_ids, visible_asset_ids_for
from django.contrib.auth.models import Group, Permission, User
from group.models import GroupAssetScope


def _ids(user):
    ids = visible_asset_ids(user)
    return set(InventoryBase.objects.filter(pk__in=ids).values_list("pk", flat=True))


def _scope(group_name, asset_groups):
    group = Group.objects.create(name=group_name)
    GroupAssetScope.objects.create(group=group).asset_groups.set(asset_groups)
    return group


@pytest.mark.django_db
class TestVisibleAssetIds:
    def test_superuser_is_not_restricted(self, admin_user, scope_setup):
        assert visible_asset_ids(admin_user) is None

    def test_user_without_scope_is_not_restricted(self, make_scoped_user):
        assert visible_asset_ids(make_scoped_user()) is None

    def test_scoped_user_sees_scope_assets_only(self, make_scoped_user, scope_setup):
        user = make_scoped_user(asset_groups=[scope_setup.paris])
        assert _ids(user) == {scope_setup.visible.pk}

    def test_view_all_assets_lifts_the_scope(self, make_scoped_user, scope_setup):
        user = make_scoped_user("view_all_assets", asset_groups=[scope_setup.paris])
        assert visible_asset_ids(user) is None

    def test_scopes_of_two_groups_add_up(
        self, admin_user, make_scoped_user, scope_setup
    ):
        lyon = AssetGroup.objects.create(
            name="Lyon", user=admin_user, visibility="public"
        )
        lyon.assets.add(scope_setup.hidden)
        user = make_scoped_user(asset_groups=[scope_setup.paris])
        user.groups.add(_scope("lyon-team", [lyon]))
        assert _ids(user) == {scope_setup.visible.pk, scope_setup.hidden.pk}

    def test_unscoped_group_does_not_lift_the_scope(
        self, make_scoped_user, scope_setup
    ):
        user = make_scoped_user(asset_groups=[scope_setup.paris])
        user.groups.add(Group.objects.create(name="helpdesk"))
        assert _ids(user) == {scope_setup.visible.pk}

    def test_scope_without_asset_group_hides_everything(
        self, make_scoped_user, scope_setup
    ):
        assert _ids(make_scoped_user(asset_groups=[])) == set()

    def test_deleted_creator_empties_scope_and_hides_everything(
        self, make_scoped_user, scope_setup
    ):
        creator = User.objects.create_user(username="creator", password="password")
        lyon = AssetGroup.objects.create(name="Lyon", user=creator, visibility="public")
        lyon.assets.add(scope_setup.hidden)
        user = make_scoped_user(asset_groups=[lyon])

        creator.delete()

        assert GroupAssetScope.objects.filter(group__user=user).exists()
        assert _ids(user) == set()

    def test_emptied_scope_and_valid_scope_add_up(self, make_scoped_user, scope_setup):
        creator = User.objects.create_user(username="creator", password="password")
        lyon = AssetGroup.objects.create(name="Lyon", user=creator, visibility="public")
        user = make_scoped_user(asset_groups=[lyon])
        user.groups.add(_scope("paris-team", [scope_setup.paris]))

        creator.delete()

        assert _ids(user) == {scope_setup.visible.pk}

    def test_request_cache(self, make_scoped_user, scope_setup):
        request = SimpleNamespace(
            user=make_scoped_user(asset_groups=[scope_setup.paris])
        )
        assert visible_asset_ids_for(request) is visible_asset_ids_for(request)
        assert visible_asset_ids_for(None) is None

    def test_view_all_assets_permission_exists(self):
        assert Permission.objects.filter(
            codename="view_all_assets", content_type__app_label="inventory_base"
        ).exists()
