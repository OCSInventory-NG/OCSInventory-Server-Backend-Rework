import logging
import os
import resource
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone as dt_timezone

from django.conf import settings
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
    ProductCheck,
    Vulnerability,
)
from security.sources import nvd, osv

logger = logging.getLogger(__name__)

# A product checked less than this ago is not asked again
RECHECK = timedelta(hours=24)
# OSV advisories downloaded at the same time: one by one, a fleet of ten
# machines took more than an hour (about 3 advisories per second)
FETCH_WORKERS = 16
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


def nvd_version_key(product, version):
    """Check row of one installed version, evaluated against the product's CVEs."""
    return f"{product}|{version}"


def _date(value):
    parsed = parse_datetime(value or "")
    if parsed is not None and timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _cvss_version(vector):
    prefix = (vector or "").split("/")[0]
    return prefix.split(":", 1)[1] if prefix.startswith("CVSS:") else ""


class MemoryLimitReached(Exception):
    """The scan went over its memory ceiling: it stops, the next run resumes."""


def memory_mb():
    """Resident memory of this process in MB (Linux), else its peak."""
    try:
        with open("/proc/self/statm") as statm:
            pages = int(statm.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") // 2**20
    except (OSError, ValueError, IndexError):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


class ScanService:
    """Checks the covered products against OSV and the NVD, stores findings."""

    @classmethod
    def refresh(
        cls, osv_client=None, nvd_client=None, now=None, progress=None, memory=None
    ):
        """
        Checks what is due and returns counts. progress receives a line per
        OSV batch and per NVD product (the task's log by default; print in a
        shell). Above SECURITY_SCAN_MEMORY_LIMIT_MB the scan stops cleanly:
        what is done stays done, the next run resumes.
        """
        now = now or timezone.now()
        progress = progress or logger.info
        memory = memory or memory_mb
        limit = settings.SECURITY_SCAN_MEMORY_LIMIT_MB
        counts = Counter()

        def guard():
            used = memory()
            if used > limit:
                raise MemoryLimitReached(f"{used} MB used, limit {limit} MB")

        try:
            cls._scan_osv(osv_client or osv.OsvClient(), now, counts, progress, guard)
            cls._scan_nvd(nvd_client or nvd.NvdClient(), now, counts, progress, guard)
        except MemoryLimitReached as error:
            logger.warning("Vulnerability scan stopped: %s", error)
            progress(f"Scan stopped, memory limit reached ({error}): next run resumes")
            counts["stopped_memory"] = 1
            return dict(counts)
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

    # OSV: Linux packages. Advisories are not kept: an Ubuntu kernel advisory
    # is 350 to 700 KB of JSON listing every kernel flavor of every release,
    # and keeping them took the scan to 1.8 GB. Each one is downloaded, turned
    # into the findings of the packages that need it, and dropped; each
    # package remembers its advisories and their "modified" (in its check's
    # payload) so that an unchanged advisory is not downloaded again.

    @classmethod
    def _osv_pairs(cls):
        """{(ecosystem, name, version): (product, version)} of the covered packages."""
        pairs = {}
        for product, version, platform_key in covered_identities().filter(
            scheme="purl"
        ).values_list("product", "version", "entry__platform_key"):
            eco = osv.ecosystem(product, platform_key)
            if eco:
                pairs[(eco, osv.query_name(product), version)] = (product, version)
        return pairs

    @classmethod
    def _scan_osv(cls, client, now, counts, progress, guard):
        pairs = cls._osv_pairs()
        fresh = cls._fresh(SOURCE_OSV, [osv_key(pair) for pair in pairs], now)
        due = [pair for pair in pairs if osv_key(pair) not in fresh]
        counts["osv_skipped"] += len(pairs) - len(due)
        batches = -(-len(due) // osv.BATCH_SIZE)
        progress(
            f"OSV: {len(due)} packages to check, {len(pairs) - len(due)} "
            "checked less than 24 hours ago"
        )
        for number, start in enumerate(range(0, len(due), osv.BATCH_SIZE), 1):
            guard()
            chunk = due[start : start + osv.BATCH_SIZE]
            try:
                results = client.query(chunk)
            except Exception as error:
                for pair in chunk:
                    cls._failed(SOURCE_OSV, osv_key(pair), error, counts, "osv_failed")
                continue
            for pair in chunk:
                if pair not in results:
                    cls._failed(
                        SOURCE_OSV, osv_key(pair), "no answer", counts, "osv_failed"
                    )
            known = dict(
                ProductCheck.objects.filter(
                    source=SOURCE_OSV, key__in=[osv_key(pair) for pair in results]
                ).values_list("key", "payload")
            )
            needed = {}
            for pair, vulns in results.items():
                done = known.get(osv_key(pair)) or {}
                for vuln in vulns:
                    if done.get(vuln["id"]) != vuln.get("modified", ""):
                        needed.setdefault(vuln["id"], []).append(pair)
            found, headers, missing = cls._download(client, needed, guard)
            for pair, vulns in results.items():
                guard()
                listed = {vuln["id"]: vuln.get("modified", "") for vuln in vulns}
                not_fetched = sorted(set(listed) & missing)
                if not_fetched:
                    error = "advisories not fetched: " + ", ".join(not_fetched)
                    cls._failed(SOURCE_OSV, osv_key(pair), error, counts, "osv_failed")
                    continue
                product, version = pairs[pair]
                with transaction.atomic():
                    cls._update_osv_findings(
                        pair, product, version, listed, found, headers
                    )
                    ProductCheck.objects.update_or_create(
                        source=SOURCE_OSV,
                        key=osv_key(pair),
                        defaults={"checked_at": now, "error": "", "payload": listed},
                    )
                counts["osv_checked"] += 1
            progress(
                f"OSV batch {number}/{batches}: {len(chunk)} packages, "
                f"{len(needed) - len(missing)} advisories fetched, "
                f"{len(missing)} failed"
            )

    @staticmethod
    def _download(client, needed, guard):
        """
        Downloads the advisories in parallel. Returns {(pair, advisory_id):
        findings}, {advisory_id: header} and the ids that failed.
        """

        def fetch(advisory_id):
            # Turned into findings in the thread: only small results come back
            try:
                record = client.advisory(advisory_id)
                compact = osv.compact(record)
                header = {
                    "summary": osv.summary(record),
                    "published": compact["published"],
                    "modified": compact["modified"],
                    "vector": compact["vector"],
                }
                per_pair = {
                    pair: osv.findings(compact, pair[0], pair[1])
                    for pair in needed[advisory_id]
                }
                return advisory_id, header, per_pair, None
            except Exception as error:
                return advisory_id, None, None, error

        found, headers, missing = {}, {}, set()
        pool = ThreadPoolExecutor(max_workers=FETCH_WORKERS)
        try:
            for advisory_id, header, per_pair, error in pool.map(fetch, needed):
                if error is not None:
                    logger.warning(
                        "OSV advisory %s not fetched: %s", advisory_id, error
                    )
                    missing.add(advisory_id)
                    continue
                headers[advisory_id] = header
                for pair, findings in per_pair.items():
                    found[(pair, advisory_id)] = findings
                guard()
        finally:
            # A stop must not wait for the downloads still queued
            pool.shutdown(wait=True, cancel_futures=True)
        return found, headers, missing

    @classmethod
    def _update_osv_findings(cls, pair, product, version, listed, found, headers):
        """
        Keeps the findings of unchanged advisories, removes those of advisories
        no longer listed, writes those of the advisories just downloaded.
        """
        unchanged = [aid for aid in listed if (pair, aid) not in found]
        Finding.objects.filter(scheme="purl", product=product, version=version).exclude(
            advisory_id__in=unchanged
        ).delete()
        for advisory_id in listed:
            if (pair, advisory_id) not in found:
                continue
            header = headers[advisory_id]
            for result in found[(pair, advisory_id)]:
                vulnerability = cls._vulnerability(
                    result["cve"],
                    SOURCE_OSV,
                    osv.advisory_url(advisory_id),
                    header["summary"],
                    header["published"],
                    header["modified"],
                    header["vector"],
                    base_score(header["vector"]),
                    result["rating"],
                )
                Finding.objects.update_or_create(
                    scheme="purl",
                    product=product,
                    version=version,
                    vulnerability=vulnerability,
                    defaults={
                        "advisory_id": advisory_id,
                        "fixed_version": result["fixed_version"][:255],
                        "affected_range": result["affected_range"][:255],
                        "method": METHOD_OSV,
                        "uncertain": False,
                    },
                )

    # NVD: Windows and macOS applications

    @classmethod
    def _scan_nvd(cls, client, now, counts, progress, guard):
        products = {}
        for product, version in covered_identities().filter(scheme="cpe").values_list(
            "product", "version"
        ):
            products.setdefault(product, set()).add(version)
        fresh = cls._fresh(SOURCE_NVD, list(products), now)
        limited = False
        for number, (product, versions) in enumerate(sorted(products.items()), 1):
            guard()
            progress(
                f"NVD product {number}/{len(products)}: {product} "
                f"({'cache' if product in fresh else 'request'})"
            )
            # One product's CVE list at a time: large products hold thousands
            cves = None
            if product in fresh:
                cves = ProductCheck.objects.get(source=SOURCE_NVD, key=product).payload
            if cves is None:
                if limited:
                    # no more requests this run, cached products are still evaluated
                    continue
                try:
                    cves = client.product_cves(product)
                except nvd.RateLimited as error:
                    cls._failed(SOURCE_NVD, product, error, counts, "nvd_rate_limited")
                    limited = True
                    continue
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
                    ProductCheck.objects.update_or_create(
                        source=SOURCE_NVD,
                        key=nvd_version_key(product, version),
                        defaults={"checked_at": now, "error": ""},
                    )

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

    @classmethod
    def _cleanup(cls):
        """
        Findings and checks of products no longer covered, vulnerabilities
        without findings: a product that comes back is checked again.
        """
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

        keys = {(SOURCE_OSV, osv_key(pair)) for pair in cls._osv_pairs()}
        for scheme, product, version in current:
            if scheme == "cpe":
                keys.add((SOURCE_NVD, product))
                keys.add((SOURCE_NVD, nvd_version_key(product, version)))
        stale_checks = [
            check_id
            for check_id, source, key in ProductCheck.objects.values_list(
                "id", "source", "key"
            )
            if (source, key) not in keys
        ]
        for start in range(0, len(stale_checks), 1000):
            ProductCheck.objects.filter(
                id__in=stale_checks[start : start + 1000]
            ).delete()
