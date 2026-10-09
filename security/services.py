import logging
from collections import Counter
from datetime import timedelta, timezone as dt_timezone

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from inventory.software_identity.models import SoftwareIdentity
from security.cvss import base_score
from security.models import (
    METHOD_OSV,
    SOURCE_NVD,
    SOURCE_OSV,
    Finding,
    OsvAdvisory,
    ProductCheck,
    Vulnerability,
)
from security.sources import nvd, osv

logger = logging.getLogger(__name__)

# A product checked less than this ago is not asked again
RECHECK = timedelta(hours=24)
# Identity statuses whose products are checked, per scheme
COVERED = {"purl": ("matched",), "cpe": ("matched", "validated")}


def covered_identities():
    """Identities whose product is checked: Linux matched, Windows/macOS decided."""
    return SoftwareIdentity.objects.filter(
        Q(scheme="purl", status__in=COVERED["purl"])
        | Q(scheme="cpe", status__in=COVERED["cpe"])
    )


def osv_key(pair):
    return "|".join(pair)


def _date(value):
    parsed = parse_datetime(value or "")
    if parsed is not None and timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _cvss_version(vector):
    prefix = (vector or "").split("/")[0]
    return prefix.split(":", 1)[1] if prefix.startswith("CVSS:") else ""


class ScanService:
    """Checks the covered products against OSV and the NVD, stores findings."""

    @classmethod
    def refresh(cls, osv_client=None, nvd_client=None, now=None):
        now = now or timezone.now()
        counts = Counter()
        cls._scan_osv(osv_client or osv.OsvClient(), now, counts)
        cls._scan_nvd(nvd_client or nvd.NvdClient(), now, counts)
        cls._cleanup()
        return dict(counts)

    @staticmethod
    def _fresh(source, keys, now):
        return set(
            ProductCheck.objects.filter(
                source=source,
                key__in=keys,
                error="",
                checked_at__gte=now - RECHECK,
            ).values_list("key", flat=True)
        )

    @staticmethod
    def _failed(source, key, error, counts, counter):
        logger.warning("Vulnerability check failed for %s %s: %s", source, key, error)
        ProductCheck.objects.update_or_create(
            source=source, key=key, defaults={"error": str(error)[:1000]}
        )
        counts[counter] += 1

    @staticmethod
    def _vulnerability(vuln_id, source, url, summary, published, modified, vector,
                       score, rating):
        """
        The vulnerability, created with these details, or completed: a later
        source only fills an empty CVSS vector and an empty rating.
        """
        vulnerability, created = Vulnerability.objects.get_or_create(
            vuln_id=vuln_id,
            defaults={
                "source": source,
                "url": url,
                "summary": summary,
                "published": _date(published),
                "modified": _date(modified),
                "cvss_version": _cvss_version(vector),
                "cvss_vector": vector or "",
                "cvss_score": score,
                "distro_rating": rating or "",
            },
        )
        if not created:
            changed = False
            if vector and not vulnerability.cvss_vector:
                vulnerability.cvss_vector = vector
                vulnerability.cvss_version = _cvss_version(vector)
                vulnerability.cvss_score = score
                changed = True
            if rating and not vulnerability.distro_rating:
                vulnerability.distro_rating = rating
                changed = True
            if changed:
                vulnerability.save()
        return vulnerability

    # OSV: Linux packages

    @classmethod
    def _osv_pairs(cls):
        """{(ecosystem, name, version): (product, version)} of the covered packages."""
        pairs = {}
        for product, version, platform_key in covered_identities().filter(
            scheme="purl"
        ).values_list("product", "version", "entry__platform_key"):
            eco = osv.ecosystem(product, platform_key)
            if eco:
                pairs[(eco, osv.package_name(product), version)] = (product, version)
        return pairs

    @classmethod
    def _scan_osv(cls, client, now, counts):
        pairs = cls._osv_pairs()
        fresh = cls._fresh(SOURCE_OSV, [osv_key(pair) for pair in pairs], now)
        due = [pair for pair in pairs if osv_key(pair) not in fresh]
        counts["osv_skipped"] += len(pairs) - len(due)
        for start in range(0, len(due), osv.BATCH_SIZE):
            chunk = due[start : start + osv.BATCH_SIZE]
            try:
                results = client.query(chunk)
            except Exception as error:
                for pair in chunk:
                    cls._failed(SOURCE_OSV, osv_key(pair), error, counts, "osv_failed")
                continue
            advisories, missing = cls._advisories(client, results)
            for pair, vulns in results.items():
                not_fetched = sorted({v["id"] for v in vulns} & missing)
                if not_fetched:
                    error = "advisories not fetched: " + ", ".join(not_fetched)
                    cls._failed(SOURCE_OSV, osv_key(pair), error, counts, "osv_failed")
                    continue
                product, version = pairs[pair]
                with transaction.atomic():
                    cls._replace_osv_findings(pair, product, version, vulns, advisories)
                    ProductCheck.objects.update_or_create(
                        source=SOURCE_OSV,
                        key=osv_key(pair),
                        defaults={"checked_at": now, "error": ""},
                    )
                counts["osv_checked"] += 1

    @staticmethod
    def _advisories(client, results):
        """
        {advisory_id: OsvAdvisory} of the results, fetched when new or
        modified, and the set of ids that could not be fetched.
        """
        wanted = {v["id"]: v.get("modified", "") for vs in results.values() for v in vs}
        cached = {
            advisory.advisory_id: advisory
            for advisory in OsvAdvisory.objects.filter(advisory_id__in=wanted)
        }
        missing = set()
        for advisory_id, modified in wanted.items():
            known = cached.get(advisory_id)
            if known is not None and known.modified == modified:
                continue
            try:
                record = client.advisory(advisory_id)
            except Exception as error:
                logger.warning("OSV advisory %s not fetched: %s", advisory_id, error)
                missing.add(advisory_id)
                continue
            cached[advisory_id], _ = OsvAdvisory.objects.update_or_create(
                advisory_id=advisory_id,
                defaults={
                    "modified": modified,
                    "summary": osv.summary(record),
                    "record": osv.compact(record),
                },
            )
        return cached, missing

    @classmethod
    def _replace_osv_findings(cls, pair, product, version, vulns, advisories):
        eco, name, _ = pair
        Finding.objects.filter(scheme="purl", product=product, version=version).delete()
        for vuln in vulns:
            advisory = advisories[vuln["id"]]
            record = advisory.record
            for found in osv.findings(record, eco, name):
                vulnerability = cls._vulnerability(
                    found["cve"],
                    SOURCE_OSV,
                    osv.advisory_url(advisory.advisory_id),
                    advisory.summary,
                    record.get("published"),
                    record.get("modified"),
                    record.get("vector"),
                    base_score(record.get("vector")),
                    found["rating"],
                )
                Finding.objects.update_or_create(
                    scheme="purl",
                    product=product,
                    version=version,
                    vulnerability=vulnerability,
                    defaults={
                        "advisory_id": advisory.advisory_id,
                        "fixed_version": found["fixed_version"][:255],
                        "affected_range": found["affected_range"][:255],
                        "method": METHOD_OSV,
                        "uncertain": False,
                    },
                )

    # NVD: Windows and macOS applications

    @classmethod
    def _scan_nvd(cls, client, now, counts):
        products = {}
        for product, version in covered_identities().filter(scheme="cpe").values_list(
            "product", "version"
        ):
            products.setdefault(product, set()).add(version)
        fresh = cls._fresh(SOURCE_NVD, list(products), now)
        cached = dict(
            ProductCheck.objects.filter(source=SOURCE_NVD, key__in=fresh).values_list(
                "key", "payload"
            )
        )
        for product, versions in sorted(products.items()):
            cves = cached.get(product)
            if cves is None:
                try:
                    cves = client.product_cves(product)
                except nvd.RateLimited as error:
                    cls._failed(SOURCE_NVD, product, error, counts, "nvd_rate_limited")
                    break
                except Exception as error:
                    cls._failed(SOURCE_NVD, product, error, counts, "nvd_failed")
                    continue
                ProductCheck.objects.update_or_create(
                    source=SOURCE_NVD,
                    key=product,
                    defaults={"checked_at": now, "error": "", "payload": cves},
                )
                counts["nvd_checked"] += 1
            else:
                counts["nvd_skipped"] += 1
            with transaction.atomic():
                for version in versions:
                    cls._replace_nvd_findings(product, version, cves)

    @classmethod
    def _replace_nvd_findings(cls, product, version, cves):
        Finding.objects.filter(scheme="cpe", product=product, version=version).delete()
        for cve in cves:
            result = nvd.evaluate(cve, version)
            if result is None:
                continue
            vulnerability = cls._vulnerability(
                cve["id"],
                SOURCE_NVD,
                nvd.cve_url(cve["id"]),
                cve.get("description", ""),
                cve.get("published"),
                cve.get("modified"),
                cve.get("cvss_vector"),
                cve.get("cvss_score"),
                "",
            )
            Finding.objects.update_or_create(
                scheme="cpe",
                product=product,
                version=version,
                vulnerability=vulnerability,
                defaults={
                    "advisory_id": cve["id"],
                    "fixed_version": result["fixed_version"][:255],
                    "affected_range": result["affected_range"][:255],
                    "method": result["method"],
                    "uncertain": result["uncertain"],
                },
            )

    @staticmethod
    def _cleanup():
        """Findings of products no longer covered, vulnerabilities without findings."""
        current = set(covered_identities().values_list("scheme", "product", "version"))
        stale = [
            finding_id
            for finding_id, *triple in Finding.objects.values_list(
                "id", "scheme", "product", "version"
            )
            if tuple(triple) not in current
        ]
        for start in range(0, len(stale), 1000):
            Finding.objects.filter(id__in=stale[start : start + 1000]).delete()
        Vulnerability.objects.filter(findings__isnull=True).delete()
