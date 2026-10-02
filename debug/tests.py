import pytest
from django.contrib.auth.models import Group, Permission
from mgmt.management.commands.migrate import Command as MigrateCommand


@pytest.mark.django_db
def test_debug_mode_permission_exists():
    permission = Permission.objects.get(
        content_type__app_label="debug", codename="view_debugmode"
    )
    assert permission.name == "Can view debug mode"


@pytest.mark.django_db
def test_default_groups_get_debug_mode_permission():
    MigrateCommand().assign_group_permissions()

    for group_name in ("super-admin", "admin", "user"):
        group = Group.objects.get(name=group_name)
        assert group.permissions.filter(
            content_type__app_label="debug", codename="view_debugmode"
        ).exists()
