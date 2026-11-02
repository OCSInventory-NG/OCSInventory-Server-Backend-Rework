# Generated manually

from django.db import migrations


def create_snmp_scanner_group(apps, schema_editor):
    """
    Create the service group used by the OCS SNMP scanner.
    """
    Group = apps.get_model("auth", "Group")
    GroupProtection = apps.get_model("group", "GroupProtection")

    group, _ = Group.objects.get_or_create(name="SnmpScanner")
    GroupProtection.objects.update_or_create(
        group_id=group.id,
        defaults={"is_protected": True},
    )


def remove_snmp_scanner_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="SnmpScanner").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("group", "0003_add_agent_groups"),
    ]

    operations = [
        migrations.RunPython(create_snmp_scanner_group, remove_snmp_scanner_group),
    ]
