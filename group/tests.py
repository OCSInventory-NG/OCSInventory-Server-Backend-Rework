import pytest
from django.contrib.auth.models import Group
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
