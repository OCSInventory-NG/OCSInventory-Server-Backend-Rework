import re

from django.db import migrations, models

# security.sources.nvd.ERRATA, as it is when this migration is written
ERRATA = ("CVE-2024-20701",)


def _major_digits(version):
    major = re.match(r"\d+", version or "")
    return len(major.group(0)) if major else 0


def _same_numbering(version, bounds):
    return all(
        abs(_major_digits(version) - _major_digits(bound)) < 2
        for bound in bounds.values()
    )


def drop_uncertain(apps, schema_editor):
    """
    Only sure NVD findings are kept: those of an "all versions" match or of
    a condition on another product (uncertain), of a CVE whose NVD data is
    wrong, or of a bound in another numbering go, open or closed. The full
    NVD years are loaded again by the next synchronization, to know the
    operating systems a CVE requires, and the Windows and macOS evaluations
    are made again by the next scan.
    """
    Finding = apps.get_model("security", "Finding")
    Exposure = apps.get_model("security", "Exposure")
    Evaluation = apps.get_model("security", "Evaluation")
    NvdMatch = apps.get_model("security", "NvdMatch")
    SourceSync = apps.get_model("security", "SourceSync")
    Vulnerability = apps.get_model("security", "Vulnerability")

    for model in (Finding, Exposure):
        model.objects.filter(uncertain=True).delete()
        model.objects.filter(method="nvd_all_versions").delete()
        model.objects.filter(vulnerability__vuln_id__in=ERRATA).delete()

    # A range whose every bound for the product counts versions otherwise
    bounds = {}
    for cve_id, product, match_bounds in NvdMatch.objects.exclude(
        bounds={}
    ).values_list("cve__cve_id", "vendor_product", "bounds"):
        bounds.setdefault((cve_id, product), []).append(match_bounds)

    def other_numbering(cve_id, product, version):
        ranges = bounds.get((cve_id, product))
        return bool(ranges) and not any(
            _same_numbering(version, rng) for rng in ranges
        )

    findings = [
        finding_id
        for finding_id, cve_id, product, version in Finding.objects.filter(
            method="nvd_range"
        ).values_list(
            "id",
            "vulnerability__vuln_id",
            "evaluation__product",
            "evaluation__version",
        )
        if other_numbering(cve_id, product, version)
    ]
    exposures = [
        exposure_id
        for exposure_id, cve_id, product, version in Exposure.objects.filter(
            method="nvd_range"
        ).values_list("id", "vulnerability__vuln_id", "product", "version")
        if other_numbering(cve_id, product, version)
    ]
    for ids, model in ((findings, Finding), (exposures, Exposure)):
        for start in range(0, len(ids), 900):
            model.objects.filter(id__in=ids[start : start + 900]).delete()

    sync = SourceSync.objects.filter(source="nvd").first()
    if sync is not None:
        years = (sync.fingerprint or {}).get("years") or {}
        for entry in years.values():
            if entry.get("full"):
                entry["sha256"] = ""
        sync.save(update_fields=["fingerprint"])
    Evaluation.objects.filter(scheme="cpe").update(sources={})
    Vulnerability.objects.filter(
        findings__isnull=True, exposures__isnull=True
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("security", "0009_drop_other_module_stream_fixes"),
    ]

    operations = [
        migrations.AddField(
            model_name="nvdmatch",
            name="systems",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(drop_uncertain, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="exposure",
            name="uncertain",
        ),
        migrations.RemoveField(
            model_name="finding",
            name="uncertain",
        ),
        migrations.AlterField(
            model_name="exposure",
            name="method",
            field=models.CharField(
                choices=[
                    ("osv", "osv"),
                    ("nvd_range", "nvd_range"),
                    ("nvd_exact", "nvd_exact"),
                ],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="finding",
            name="method",
            field=models.CharField(
                choices=[
                    ("osv", "osv"),
                    ("nvd_range", "nvd_range"),
                    ("nvd_exact", "nvd_exact"),
                ],
                max_length=16,
            ),
        ),
    ]
