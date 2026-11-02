import datetime

from django.db import migrations

# (base, version, codename, end of standard support). Ubuntu LTS dates as
# published by Canonical: from then on, the release's packages are also
# checked against its Ubuntu Pro advisories. Interim releases have no Pro.
RELEASES = [
    ("debian", "10", "buster", None),
    ("debian", "11", "bullseye", None),
    ("debian", "12", "bookworm", None),
    ("debian", "13", "trixie", None),
    ("ubuntu", "16.04", "xenial", datetime.date(2021, 4, 30)),
    ("ubuntu", "18.04", "bionic", datetime.date(2023, 5, 31)),
    ("ubuntu", "20.04", "focal", datetime.date(2025, 5, 31)),
    ("ubuntu", "22.04", "jammy", datetime.date(2027, 6, 1)),
    ("ubuntu", "24.04", "noble", datetime.date(2029, 6, 1)),
    ("ubuntu", "24.10", "oracular", datetime.date(2025, 7, 10)),
    ("ubuntu", "25.04", "plucky", datetime.date(2026, 1, 15)),
    ("ubuntu", "25.10", "questing", datetime.date(2026, 7, 1)),
]

# Mapping attribute: (section, field) of the default templates
LINUX = {
    "architecture": ("SOFTWARES", "ARCHITECTURE"),
    "package_format": ("SOFTWARES", "FROM"),
    "source_package": ("SOFTWARES", "SOURCE"),
    "source_version": ("SOFTWARES", "SOURCE VERSION"),
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
    ("Linux (Debian based)", "DEB"): {
        **LINUX,
        "package_origin": ("SOFTWARES", "ORIGIN"),
    },
    # The RPM Vendor, already collected as the publisher, is the origin
    ("Linux (RHEL based)", "RHEL"): {
        **LINUX,
        "package_origin": ("SOFTWARES", "PUBLISHER"),
    },
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


def seed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    Template = apps.get_model("template", "Template")
    Field = apps.get_model("field", "Field")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    DistroRelease.objects.bulk_create(
        [
            DistroRelease(
                base=base, version=version, codename=codename, standard_support_end=end
            )
            for base, version, codename, end in RELEASES
        ]
    )

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


def unseed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    Template = apps.get_model("template", "Template")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    DistroRelease.objects.filter(
        codename__in=[codename for _, _, codename, _ in RELEASES]
    ).delete()
    for (name, os_type), attributes in DEFAULT_MAPPINGS.items():
        SoftwareMapping.objects.filter(
            template=Template.objects.get(name=name, os=os_type)
        ).update(**dict.fromkeys(attributes))


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0007_software_identity"),
        ("field", "0014_software_identity_fields"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
