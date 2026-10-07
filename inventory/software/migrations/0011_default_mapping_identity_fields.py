from django.db import migrations

LINUX = {
    "architecture": ("SOFTWARES", "ARCHITECTURE"),
    "package_format": ("SOFTWARES", "FROM"),
    "source_package": ("SOFTWARES", "SOURCE"),
    "os_id": ("OS RELEASE", "ID"),
    "os_like": ("OS RELEASE", "ID_LIKE"),
    "os_release": ("OS RELEASE", "VERSION_ID"),
    "os_codename": ("OS RELEASE", "CODENAME"),
    "running_kernel": ("OS RELEASE", "RUNNING_KERNEL"),
}
OPERATING_SYSTEM = {
    "os_id": ("OPERATING SYSTEM", "OS NAME"),
    "os_release": ("OPERATING SYSTEM", "OS VERSION"),
}

DEFAULT_MAPPINGS = {
    ("Linux (Debian based)", "DEB"): LINUX,
    ("Linux (RHEL based)", "RHEL"): LINUX,
    ("Windows", "WIN"): OPERATING_SYSTEM,
    ("MacOS", "MAC"): OPERATING_SYSTEM,
    # Old agents do not run templates: OS name and version of HARDWARE, and
    # no source package (the Legacy SOURCE field is the install source)
    ("Legacy", "LEG"): {
        "os_id": ("HARDWARE", "OPERATING SYSTEM"),
        "os_release": ("HARDWARE", "OS VERSION"),
        "architecture": ("SOFTWARES", "ARCHITECTURE"),
        "package_format": ("SOFTWARES", "FROM"),
    },
}


def set_default_mapping_fields(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    Field = apps.get_model("field", "Field")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    for (name, os_type), attributes in DEFAULT_MAPPINGS.items():
        template = Template.objects.get(name=name, os=os_type)
        mapping = SoftwareMapping.objects.get(template=template)
        for attribute, (section_name, field_name) in attributes.items():
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
            setattr(mapping, attribute, field)
        mapping.save()


def clear_default_mapping_fields(apps, schema_editor):
    Template = apps.get_model("template", "Template")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    for (name, os_type), attributes in DEFAULT_MAPPINGS.items():
        SoftwareMapping.objects.filter(
            template=Template.objects.get(name=name, os=os_type)
        ).update(**dict.fromkeys(attributes))


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0010_assetplatform_dictionary_platform"),
        ("field", "0014_software_identity_fields"),
    ]

    operations = [
        migrations.RunPython(
            set_default_mapping_fields, reverse_code=clear_default_mapping_fields
        ),
    ]
