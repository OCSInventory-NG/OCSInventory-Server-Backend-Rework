from django.db import migrations


def create_windows_extended_template(apps, schema_editor):
    Template = apps.get_model("template", "Template")

    try:
        Template.objects.create(
            name="Windows Extended",
            os="WIN",
            is_protected=True,
        )
    except Exception as e:
        print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("template", "0003_legacy_extended"),
        ("field", "0010_legacy_extended"),
    ]

    operations = [
        migrations.RunPython(create_windows_extended_template),
    ]
