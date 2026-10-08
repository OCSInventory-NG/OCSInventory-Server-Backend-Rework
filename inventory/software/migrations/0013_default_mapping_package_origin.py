from django.db import migrations

# (template, os): (section, field) holding the package origin
DEFAULT_ORIGINS = {
    ("Linux (Debian based)", "DEB"): ("SOFTWARES", "ORIGIN"),
    # The RPM Vendor, already collected as the publisher
    ("Linux (RHEL based)", "RHEL"): ("SOFTWARES", "PUBLISHER"),
}


def set_default_package_origin(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Field = apps.get_model("field", "Field")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    for (name, os_type), (section_name, field_name) in DEFAULT_ORIGINS.items():
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
        SoftwareMapping.objects.filter(template=template).update(package_origin=field)


def clear_default_package_origin(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    for name, os_type in DEFAULT_ORIGINS:
        SoftwareMapping.objects.filter(
            template=Template.objects.get(name=name, os=os_type)
        ).update(package_origin=None)


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0012_package_origin"),
        ("field", "0015_package_origin_field"),
    ]

    operations = [
        migrations.RunPython(
            set_default_package_origin, reverse_code=clear_default_package_origin
        ),
    ]
