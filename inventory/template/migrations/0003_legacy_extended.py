from django.db import migrations


def create_legacy_extended_template(apps, schema_editor):
    Template = apps.get_model("template", "Template")

    try:
        Template.objects.create(
            name="Legacy Extended",
            os="LEG",
            is_protected=True,
        )
    except Exception as e:
        print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("template", "0002_templateversion"),
    ]

    operations = [
        migrations.RunPython(create_legacy_extended_template),
    ]
