from django.db import migrations
from django.db.models import Q

# security.kernel.is_noise: without a fix, on the kernel or on mozjs
KERNEL_SOURCES = r"^pkg:(deb/[^/]+/linux(-signed.*|-hwe.*)?|rpm/[^/]+/kernel)$"
MOZJS = r"^pkg:[a-z]+/[^/]+/mozjs[0-9]+$"


def drop_noise(apps, schema_editor):
    """
    The evaluations and the scan no longer keep the noise: its stored
    findings and exposures go, open or closed, then the vulnerabilities
    nothing refers to.
    """
    Finding = apps.get_model("security", "Finding")
    Exposure = apps.get_model("security", "Exposure")
    Vulnerability = apps.get_model("security", "Vulnerability")
    Exposure.objects.filter(
        Q(kernel=True) | Q(product__regex=MOZJS), fixed_version=""
    ).delete()
    Finding.objects.filter(
        Q(evaluation__product__regex=KERNEL_SOURCES)
        | Q(evaluation__product__regex=MOZJS),
        fixed_version="",
    ).delete()
    Vulnerability.objects.filter(findings__isnull=True, exposures__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0007_osv_redhat_source"),
    ]

    operations = [
        migrations.RunPython(drop_noise, migrations.RunPython.noop),
    ]
