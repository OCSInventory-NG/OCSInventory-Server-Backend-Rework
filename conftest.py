import pytest
from django.contrib.auth.models import Permission, User
from rest_framework.test import APIClient


@pytest.fixture
def admin_user(db):
    """
    A superuser, bypasses DjangoModelPermissions entirely.

    Named differently from "admin": the user.0001_initial data migration
    already creates a superuser with that username.
    """
    return User.objects.create_superuser(
        username="test-superuser", email="test-superuser@example.com", password="password"
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
