from django.db import migrations

LEGACY_ENTRY = {
    "name": "legacy_duplicate_reconciliation",
    "description": "Field(s) used to reconcile duplicate computers "
    "on the legacy endpoint",
    "value": ["uuid"],
    "type": "multiselect",
    "unit": "",
    "options": ["uuid", "name", "serial", "srcmac"],
}


def add_legacy_reconciliation(apps, schema_editor):
    Config = apps.get_model("config", "Config")
    try:
        server = Config.objects.get(name="server")
    except Config.DoesNotExist:
        return

    value = server.value
    if any(item.get("name") == LEGACY_ENTRY["name"] for item in value):
        return

    # insert right below the 3.x "duplicate_reconciliation" entry
    index = len(value)
    for i, item in enumerate(value):
        if item.get("name") == "duplicate_reconciliation":
            index = i + 1
            break

    value.insert(index, LEGACY_ENTRY)
    server.value = value
    server.save()


def remove_legacy_reconciliation(apps, schema_editor):
    Config = apps.get_model("config", "Config")
    try:
        server = Config.objects.get(name="server")
    except Config.DoesNotExist:
        return

    server.value = [
        item for item in server.value if item.get("name") != LEGACY_ENTRY["name"]
    ]
    server.save()


class Migration(migrations.Migration):

    dependencies = [
        ("config", "0003_add_max_template_versions"),
    ]

    operations = [
        migrations.RunPython(add_legacy_reconciliation, remove_legacy_reconciliation),
    ]
