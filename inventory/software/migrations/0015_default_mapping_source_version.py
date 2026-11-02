from django.db import migrations

TEMPLATES = (("Linux (Debian based)", "DEB"), ("Linux (RHEL based)", "RHEL"))
FIELD = ("SOFTWARES", "SOURCE VERSION")


def set_default_source_version(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Field = apps.get_model("field", "Field")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    section_name, field_name = FIELD
    for name, os_type in TEMPLATES:
        template = Template.objects.get(name=name, os=os_type)
        field = (
            Field.objects.filter(
                section__template=template,
                section__name=section_name,
                name=field_name,
            )
            .order_by("id")
            .first()
        )
        if field is None:
            raise ValueError(f"{name}: field {section_name} {field_name} not found")
        SoftwareMapping.objects.filter(template=template).update(source_version=field)


def clear_default_source_version(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    for name, os_type in TEMPLATES:
        SoftwareMapping.objects.filter(
            template=Template.objects.get(name=name, os=os_type)
        ).update(source_version=None)


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0014_source_version"),
        ("field", "0016_source_version_field"),
    ]

    operations = [
        migrations.RunPython(
            set_default_source_version, reverse_code=clear_default_source_version
        ),
    ]
