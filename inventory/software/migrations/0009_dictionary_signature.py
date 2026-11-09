import hashlib
import json
from collections import defaultdict

from django.db import migrations, models

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
    keeps its first entry, which takes the machines, the identity and the
    security exposures of the others; then every entry gets its signature.
    """
    Entry = apps.get_model("software", "SoftwareDictionary")
    Link = Entry.assets.through
    Identity = apps.get_model("software_identity", "SoftwareIdentity")
    Exposure = apps.get_model("security", "Exposure")

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
        if not Identity.objects.filter(entry_id=kept).exists():
            moved = Identity.objects.filter(entry_id__in=others).order_by("id").first()
            if moved is not None:
                Identity.objects.filter(pk=moved.pk).update(entry_id=kept)
        Identity.objects.filter(entry_id__in=others).delete()
        Exposure.objects.filter(entry_id__in=others).update(entry_id=kept)
        Entry.objects.filter(id__in=others).delete()
        Entry.objects.filter(id=kept).update(installation_number=len(machines))

    signatures = {ids[0]: signature for signature, ids in groups.items()}
    entries = list(Entry.objects.only("id"))
    for entry in entries:
        entry.signature = signatures[entry.id]
    Entry.objects.bulk_update(entries, ["signature"], batch_size=BATCH)


class Migration(migrations.Migration):
    dependencies = [
        ("software", "0008_seed_software_identity"),
        ("software_identity", "0002_seed"),
        ("security", "0006_drop_minor_debian_urgencies"),
    ]

    operations = [
        migrations.AddField(
            model_name="softwaredictionary",
            name="signature",
            field=models.CharField(editable=False, max_length=64, null=True),
        ),
        migrations.RunPython(merge_duplicates, migrations.RunPython.noop),
    ]
