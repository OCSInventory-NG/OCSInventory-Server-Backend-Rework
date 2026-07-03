from django.db import migrations


def add_max_template_versions_config(apps, schema_editor):
    Config = apps.get_model("config", "Config")
    try:
        server_config = Config.objects.get(name="server")
    except Config.DoesNotExist:
        return

    if any(item.get("name") == "max_template_versions" for item in server_config.value):
        return

    server_config.value.append(
        {
            "name": "max_template_versions",
            "description": "Maximum number of version snapshots to keep per template",
            "value": 20,
            "type": "number input",
            "unit": "",
        }
    )
    server_config.save()


def remove_max_template_versions_config(apps, schema_editor):
    Config = apps.get_model("config", "Config")
    try:
        server_config = Config.objects.get(name="server")
    except Config.DoesNotExist:
        return

    server_config.value = [
        item for item in server_config.value if item.get("name") != "max_template_versions"
    ]
    server_config.save()


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0002_alter_config_options"),
    ]

    operations = [
        migrations.RunPython(
            add_max_template_versions_config, remove_max_template_versions_config
        ),
    ]
