from django.db import migrations


def create_default_macos_software_mapping(apps, schema_editor):
    Template = apps.get_model("template", "Template").objects.get(os="MAC")
    Section = apps.get_model("section", "Section").objects.get(
        name="SOFTWARES",
        template=Template,
    )

    software_mapping = {
        "template": Template,
        "section": Section,
        "name": apps.get_model("field", "Field").objects.get(
            name="NAME",
            section=Section,
        ),
        "publisher": apps.get_model("field", "Field").objects.get(
            name="PUBLISHER",
            section=Section,
        ),
        "version": apps.get_model("field", "Field").objects.get(
            name="VERSION",
            section=Section,
        ),
        "major_version": apps.get_model("field", "Field").objects.get(
            name="MAJOR",
            section=Section,
        ),
        "minor_version": apps.get_model("field", "Field").objects.get(
            name="MINOR",
            section=Section,
        ),
        "patch_version": apps.get_model("field", "Field").objects.get(
            name="PATCH",
            section=Section,
        ),
    }

    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    try:
        SoftwareMapping.objects.create(**software_mapping)
    except Exception as e:
        print(e)


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_macos_software_mapping),
    ]