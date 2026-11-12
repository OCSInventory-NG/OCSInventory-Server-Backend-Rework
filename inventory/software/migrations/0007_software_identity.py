import datetime
import hashlib
import json
from collections import defaultdict

import django.db.models.deletion
from django.db import migrations, models

# (base, version, codename, end of standard support, end of every security
# support). Ubuntu LTS standard support as published by Canonical: from then
# on, the release's packages are also checked against its Ubuntu Pro
# advisories; interim releases have no Pro. End of every security support:
# Debian, end of its LTS; Ubuntu LTS, end of Ubuntu Pro (ESM), the Legacy
# add-on left out; interim releases, their end of life.
RELEASES = [
    ("debian", "10", "buster", None, datetime.date(2024, 6, 30)),
    ("debian", "11", "bullseye", None, datetime.date(2026, 8, 31)),
    ("debian", "12", "bookworm", None, datetime.date(2028, 6, 30)),
    ("debian", "13", "trixie", None, datetime.date(2030, 6, 30)),
    (
        "ubuntu",
        "16.04",
        "xenial",
        datetime.date(2021, 4, 30),
        datetime.date(2026, 4, 30),
    ),
    (
        "ubuntu",
        "18.04",
        "bionic",
        datetime.date(2023, 5, 31),
        datetime.date(2028, 5, 31),
    ),
    (
        "ubuntu",
        "20.04",
        "focal",
        datetime.date(2025, 5, 31),
        datetime.date(2030, 5, 31),
    ),
    ("ubuntu", "22.04", "jammy", datetime.date(2027, 6, 1), datetime.date(2032, 6, 1)),
    ("ubuntu", "24.04", "noble", datetime.date(2029, 6, 1), datetime.date(2034, 6, 1)),
    (
        "ubuntu",
        "24.10",
        "oracular",
        datetime.date(2025, 7, 10),
        datetime.date(2025, 7, 10),
    ),
    (
        "ubuntu",
        "25.04",
        "plucky",
        datetime.date(2026, 1, 15),
        datetime.date(2026, 1, 15),
    ),
    (
        "ubuntu",
        "25.10",
        "questing",
        datetime.date(2026, 7, 1),
        datetime.date(2026, 7, 1),
    ),
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


def check_constraints_now(schema_editor):
    """
    PostgreSQL alters no table with deferred constraint checks pending in
    the transaction: the indexes of this migration come last, and when it is
    reversed, the schema operations come after the unseed.
    """
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def seed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    Template = apps.get_model("template", "Template")
    Field = apps.get_model("field", "Field")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    DistroRelease.objects.bulk_create(
        [
            DistroRelease(
                base=base,
                version=version,
                codename=codename,
                standard_support_end=standard_end,
                support_end=end,
            )
            for base, version, codename, standard_end, end in RELEASES
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
    check_constraints_now(schema_editor)


def unseed(apps, schema_editor):
    DistroRelease = apps.get_model("software", "DistroRelease")
    Template = apps.get_model("template", "Template")
    SoftwareMapping = apps.get_model("software", "SoftwareMapping")

    DistroRelease.objects.filter(
        codename__in=[codename for _, _, codename, _, _ in RELEASES]
    ).delete()
    for (name, os_type), attributes in DEFAULT_MAPPINGS.items():
        SoftwareMapping.objects.filter(
            template=Template.objects.get(name=name, os=os_type)
        ).update(**dict.fromkeys(attributes))
    check_constraints_now(schema_editor)


# As inventory.software.models at this migration
SIGNATURE_FIELDS = (
    "name",
    "publisher",
    "version",
    "major_version",
    "minor_version",
    "patch_version",
    "platform_family",
    "platform_key",
    "architecture",
    "package_format",
    "source_package",
    "source_version",
    "package_origin",
)
BATCH = 1000


def signature_of(row):
    parts = [None if row[name] is None else str(row[name]) for name in SIGNATURE_FIELDS]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def merge_duplicates(apps, schema_editor):
    """
    Entries created twice by inventories received at once: each signature
    keeps its first entry, which takes the machines of the others; then
    every entry gets its signature.
    """
    Entry = apps.get_model("software", "SoftwareDictionary")
    Link = Entry.assets.through

    groups = defaultdict(list)
    for row in Entry.objects.order_by("id").values("id", *SIGNATURE_FIELDS):
        groups[signature_of(row)].append(row["id"])

    for ids in groups.values():
        if len(ids) < 2:
            continue
        kept, others = ids[0], ids[1:]
        machines = set(
            Link.objects.filter(softwaredictionary_id=kept).values_list(
                "inventorybase_id", flat=True
            )
        )
        for link in Link.objects.filter(softwaredictionary_id__in=others):
            if link.inventorybase_id in machines:
                link.delete()
            else:
                machines.add(link.inventorybase_id)
                Link.objects.filter(pk=link.pk).update(softwaredictionary_id=kept)
        Entry.objects.filter(id__in=others).delete()
        Entry.objects.filter(id=kept).update(installation_number=len(machines))

    signatures = {ids[0]: signature for signature, ids in groups.items()}
    entries = list(Entry.objects.only("id"))
    for entry in entries:
        entry.signature = signatures[entry.id]
    Entry.objects.bulk_update(entries, ["signature"], batch_size=BATCH)
    check_constraints_now(schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ("field", "0014_software_identity_fields"),
        ("inventory_base", "0001_initial"),
        ("software", "0006_legacy"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetPlatform",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("os_id", models.CharField(blank=True, default="", max_length=255)),
                ("os_like", models.CharField(blank=True, default="", max_length=255)),
                (
                    "os_release",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "os_codename",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "running_kernel",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("family", models.CharField(blank=True, default="", max_length=16)),
                ("key", models.CharField(blank=True, default="", max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="DistroRelease",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("base", models.CharField(max_length=32)),
                ("version", models.CharField(max_length=16)),
                ("codename", models.CharField(max_length=32)),
                ("standard_support_end", models.DateField(blank=True, null=True)),
                ("support_end", models.DateField(blank=True, null=True)),
            ],
            options={
                "ordering": ["base", "version"],
            },
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="architecture",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="package_format",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="package_origin",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="platform_family",
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="platform_key",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="signature",
            field=models.CharField(
                editable=False, max_length=64, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="source_package",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="softwaredictionary",
            name="source_version",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="architecture",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_architecture_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="os_codename",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_os_codename_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="os_id",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_os_id_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="os_like",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_os_like_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="os_release",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_os_release_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="package_format",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_package_format_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="package_origin",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_package_origin_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="running_kernel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_running_kernel_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="source_package",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_source_package_mappings",
                to="field.field",
            ),
        ),
        migrations.AddField(
            model_name="softwaremapping",
            name="source_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="software_source_version_mappings",
                to="field.field",
            ),
        ),
        migrations.AddIndex(
            model_name="softwaredictionary",
            index=models.Index(
                fields=["platform_key"], name="software_so_platfor_c665cc_idx"
            ),
        ),
        migrations.AddField(
            model_name="assetplatform",
            name="asset",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="platform",
                to="inventory_base.inventorybase",
            ),
        ),
        migrations.AddConstraint(
            model_name="distrorelease",
            constraint=models.UniqueConstraint(
                fields=("base", "codename"), name="unique_distro_release_codename"
            ),
        ),
        migrations.RunPython(seed, reverse_code=unseed),
        migrations.RunPython(merge_duplicates, migrations.RunPython.noop),
    ]
