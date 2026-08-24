# Generated manually

from django.db import migrations


def create_agent_groups(apps, schema_editor):
    """
    Create the service groups used by OCS agents: AgentInventory (inventory
    reporting) and AgentDeployment (software deployment).
    """
    Group = apps.get_model("auth", "Group")
    GroupProtection = apps.get_model("group", "GroupProtection")

    for group_name in ("AgentInventory", "AgentDeployment"):
        group, _ = Group.objects.get_or_create(name=group_name)
        GroupProtection.objects.update_or_create(
            group_id=group.id,
            defaults={"is_protected": True},
        )


def remove_agent_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["AgentInventory", "AgentDeployment"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("group", "0002_groupprotection"),
    ]

    operations = [
        migrations.RunPython(create_agent_groups, remove_agent_groups),
    ]
