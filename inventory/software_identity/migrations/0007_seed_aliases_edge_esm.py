from django.db import migrations

# Products the NVD files under two names
ALIASES = [
    ("zoom:zoom", "zoom:meetings"),
    ("zoom:meetings", "zoom:zoom"),
]
# "microsoft:edge" is the EdgeHTML browser (CVEs of 2016 to 2018 for every
# version): today's Edge is microsoft:edge_chromium
DECISIONS = [
    ("windows", "microsoft edge", "microsoft:edge_chromium"),
    ("macos", "microsoft edge", "microsoft:edge_chromium"),
]
# Ubuntu Pro repositories (esm-infra, esm-apps)
EXTENDED_ORIGINS = [
    ("UbuntuESM", "ubuntu"),
    ("UbuntuESMApps", "ubuntu"),
]


def seed(apps, schema_editor):
    CpeAlias = apps.get_model("software_identity", "CpeAlias")
    IdentityDecision = apps.get_model("software_identity", "IdentityDecision")
    PackageOrigin = apps.get_model("software_identity", "PackageOrigin")
    for product, alias in ALIASES:
        CpeAlias.objects.get_or_create(
            product=product, alias=alias, defaults={"source": "shipped"}
        )
    for family, key, product in DECISIONS:
        IdentityDecision.objects.get_or_create(
            family=family,
            match_key=key,
            source="shipped",
            defaults={"product": product},
        )
    for name, distribution in EXTENDED_ORIGINS:
        if not PackageOrigin.objects.filter(name__iexact=name).exists():
            PackageOrigin.objects.create(
                name=name, distribution=distribution, extended=True
            )


def unseed(apps, schema_editor):
    CpeAlias = apps.get_model("software_identity", "CpeAlias")
    IdentityDecision = apps.get_model("software_identity", "IdentityDecision")
    PackageOrigin = apps.get_model("software_identity", "PackageOrigin")
    for product, alias in ALIASES:
        CpeAlias.objects.filter(product=product, alias=alias, source="shipped").delete()
    for family, key, _ in DECISIONS:
        IdentityDecision.objects.filter(
            family=family, match_key=key, source="shipped"
        ).delete()
    PackageOrigin.objects.filter(
        name__in=[name for name, _ in EXTENDED_ORIGINS], extended=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("software_identity", "0006_cpe_alias_extended_origin"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
