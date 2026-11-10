import re
from urllib.parse import unquote

from django.db import migrations

# security.versions.same_stream, as it is when this migration is written
MODULE_BUILD = re.compile(r"\.module[+_]el\d")
MODULE_STREAM = re.compile(r"(?<![\w.+-])([A-Za-z0-9][\w.+-]*):([A-Za-z0-9][\w.+-]*)")


def _upstream(version):
    epoch, sep, rest = version.partition(":")
    if not (sep and epoch.isdigit()):
        rest = version
    return rest.rsplit("-", 1)[0]


def same_stream(installed, fixed, package, streams):
    module_fix = (fixed and MODULE_BUILD.search(fixed)) or package in streams
    if bool(module_fix) != bool(MODULE_BUILD.search(installed)):
        return False
    stream = streams.get(package, "")
    if not MODULE_BUILD.search(installed) or not stream[:1].isdigit():
        return True
    version = _upstream(installed)
    return version == stream or version.startswith(stream + ".")


def drop_other_stream_fixes(apps, schema_editor):
    """
    The evaluations no longer keep the fix of another module stream (or of a
    module for a package outside modules): the stored findings and exposures
    go, open or closed, and the RPM evaluations are made again by the next
    scan. Then the vulnerabilities nothing refers to.
    """
    OsvAdvisory = apps.get_model("security", "OsvAdvisory")
    Finding = apps.get_model("security", "Finding")
    Exposure = apps.get_model("security", "Exposure")
    Evaluation = apps.get_model("security", "Evaluation")
    Vulnerability = apps.get_model("security", "Vulnerability")
    summaries = dict(
        OsvAdvisory.objects.filter(
            source__in=("osv_rocky", "osv_alma", "osv_redhat")
        ).values_list("advisory_id", "summary")
    )
    streams = {}

    def foreign(advisory_id, product, installed, fixed):
        if advisory_id not in summaries:
            return False
        if advisory_id not in streams:
            streams[advisory_id] = dict(MODULE_STREAM.findall(summaries[advisory_id]))
        package = unquote(product.rsplit("/", 1)[1])
        return not same_stream(installed, fixed, package, streams[advisory_id])

    rpm = {"product__startswith": "pkg:rpm/"}
    finding_rows = Finding.objects.filter(
        evaluation__product__startswith="pkg:rpm/"
    ).values_list(
        "id",
        "advisory_id",
        "evaluation__product",
        "evaluation__version",
        "fixed_version",
    )
    exposure_rows = Exposure.objects.filter(scheme="purl", **rpm).values_list(
        "id", "advisory_id", "product", "version", "fixed_version"
    )
    findings = [row[0] for row in finding_rows if foreign(*row[1:])]
    exposures = [row[0] for row in exposure_rows if foreign(*row[1:])]
    for ids, model in ((findings, Finding), (exposures, Exposure)):
        for start in range(0, len(ids), 900):
            model.objects.filter(id__in=ids[start : start + 900]).delete()
    Evaluation.objects.filter(scheme="purl", **rpm).update(sources={})
    Vulnerability.objects.filter(
        findings__isnull=True, exposures__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("security", "0008_drop_noise"),
    ]

    operations = [
        migrations.RunPython(drop_other_stream_fixes, migrations.RunPython.noop),
    ]
