from types import SimpleNamespace

import pytest
from django.contrib.auth.models import Group, Permission, User
from rest_framework.test import APIClient

from asset.inventory_base.models import InventoryBase
from asset.asset_group.models import AssetGroup
from group.models import GroupAssetScope


@pytest.fixture
def admin_user(db):
    """
    A superuser, bypasses DjangoModelPermissions entirely.

    Named differently from "admin": the user.0001_initial data migration
    already creates a superuser with that username.
    """
    return User.objects.create_superuser(
        username="test-superuser",
        email="test-superuser@example.com",
        password="password",
    )


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def make_api_client(db):
    """
    Factory to build an authenticated client for a plain (non-superuser) user,
    granted only the given Django permission codenames (e.g. "view_category").
    """

    def _make(*permission_codenames, username="user"):
        user = User.objects.create_user(username=username, password="password")
        if permission_codenames:
            perms = Permission.objects.filter(codename__in=permission_codenames)
            user.user_permissions.set(perms)
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _make


@pytest.fixture
def make_asset(db):
    def _make(name):
        return InventoryBase.objects.create(
            name=name,
            serial=f"SN-{name}",
            osname="Linux",
            uuid=f"uuid-{name}",
            # skips the automation rule engine on save
            is_template_forced=True,
        )

    return _make


@pytest.fixture
def scope_setup(admin_user, make_asset):
    """visible is in the public group Paris, hidden is in no group"""
    visible = make_asset("visible")
    hidden = make_asset("hidden")
    paris = AssetGroup.objects.create(
        name="Paris", user=admin_user, visibility="public"
    )
    paris.assets.add(visible)
    return SimpleNamespace(visible=visible, hidden=hidden, paris=paris)


@pytest.fixture
def make_scoped_user(db):
    """User in a group "<username>-group", scoped when asset_groups is a list"""

    def _make(*permission_codenames, asset_groups=None, username="scoped"):
        user = User.objects.create_user(username=username, password="password")
        user.user_permissions.set(
            Permission.objects.filter(codename__in=permission_codenames)
        )
        group = Group.objects.create(name=f"{username}-group")
        user.groups.add(group)
        if asset_groups is not None:
            GroupAssetScope.objects.create(group=group).asset_groups.set(asset_groups)
        return user

    return _make


@pytest.fixture
def client_for(db):
    def _client(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _client
