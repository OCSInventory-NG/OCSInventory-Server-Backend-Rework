import logging
import re
from datetime import date, timedelta

import requests
from django.utils import timezone

from .config import get_cve_config

LOGGER = logging.getLogger(__name__)

NVD_CVE_URL_TEMPLATE = "https://nvd.nist.gov/vuln/detail/{cve_id}"


def build_cve_url(cve_id):
    return NVD_CVE_URL_TEMPLATE.format(cve_id=cve_id)


def build_cve_summary(queryset):
    """
    Aggregate a CveReport queryset into dashboard-tile counts: CVE counts by
    CVSS severity bucket, distinct CVE/software/asset counts, and the
    highest CVSS score currently known.
    """
    from asset.inventory_base.models import InventoryBase

    severity_buckets = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
    for score in queryset.values_list("cvss_score", flat=True):
        if score is None:
            severity_buckets["unknown"] += 1
        elif score >= 9:
            severity_buckets["critical"] += 1
        elif score >= 7:
            severity_buckets["high"] += 1
        elif score >= 4:
            severity_buckets["medium"] += 1
        else:
            severity_buckets["low"] += 1

    impacted_asset_count = (
        InventoryBase.objects.filter(software_dictionary_entries__cve_reports__in=queryset)
        .distinct()
        .count()
    )

    return {
        "total_cves": queryset.values("cve_id").distinct().count(),
        "vulnerable_software_count": queryset.values("software").distinct().count(),
        "impacted_asset_count": impacted_asset_count,
        "highest_cvss_score": queryset.order_by("-cvss_score")
        .values_list("cvss_score", flat=True)
        .first(),
        "by_severity": severity_buckets,
    }

# Words that pollute name-based CPE guessing but never appear in a real
# vendor/product pair (project hosting, language runtimes, generic terms).
_NOISE_WORDS = {
    "http",
    "https",
    "www",
    "org",
    "com",
    "net",
    "io",
    "co",
    "github",
    "gitlab",
    "project",
    "foundation",
    "node",
    "python3",
    "python",
    "perl",
    "ruby",
    "golang",
    "rust",
    "php",
}

_URL_SCHEME_RE = re.compile(r"https?://")
_PARENS_RE = re.compile(r"\([^)]*\)")
_TRAILING_DIGITS_RE = re.compile(r"(?<=[a-zA-Z])\d+$")
_LIB_PREFIX_RE = re.compile(r"^lib(?=[a-zA-Z])")


def clean_tokens(name):
    """
    Clean a raw software name into tokens usable by cpe-guesser.

    Strips URL scheme, parenthesized content, purely numeric tokens, and
    digits trailing directly on a word (libmagic1 -> libmagic), plus a list
    of noise words that are never real vendor/product names.
    """
    if not name:
        return []

    text = _URL_SCHEME_RE.sub(" ", name)
    text = _PARENS_RE.sub(" ", text)

    tokens = []
    for raw_token in re.split(r"[\s\-_/]+", text):
        token = raw_token.strip().lower()
        if not token:
            continue
        if token.isdigit():
            continue
        token = _TRAILING_DIGITS_RE.sub("", token)
        if not token or token in _NOISE_WORDS:
            continue
        tokens.append(token)

    return tokens


def _strip_lib_prefix(tokens):
    """Fallback pass: strip an isolated leading `lib` prefix from tokens."""
    stripped = []
    for token in tokens:
        new_token = _LIB_PREFIX_RE.sub("", token)
        stripped.append(new_token if new_token else token)
    return stripped


def _is_placeholder_cpe(vendor, product):
    """Reject generic NVD dictionary placeholders like any_hostname_project."""
    for value in (vendor, product):
        if not value:
            continue
        value = value.lower()
        if value == "any" or value.startswith("any_"):
            return True
    return False


def _query_cpe_guesser(base_url, tokens):
    """
    Query cpe-guesser with the given tokens, return (cpe, rank) or (None, None).

    cpe-guesser's /search endpoint takes a POST with a JSON body
    {"query": [<tokens>]} and returns a list of [score, cpe_prefix] pairs
    sorted by descending score (highest score = closer match), where
    cpe_prefix is a partial "cpe:2.3:<part>:<vendor>:<product>" (no version).
    """
    if not tokens or not base_url:
        return None, None

    url = f"{base_url.rstrip('/')}/search"
    payload = {"query": tokens}
    try:
        resp = requests.post(url, json=payload, timeout=5)
        LOGGER.debug(
            "cpe-guesser POST %s payload=%s -> status=%d body=%s",
            url,
            payload,
            resp.status_code,
            resp.text[:500],
        )
        if resp.status_code != 200:
            return None, None
        results = resp.json()
    except Exception:
        LOGGER.exception("cpe-guesser query failed for tokens=%s", tokens)
        return None, None

    if not results:
        return None, None

    for candidate in results:
        if not isinstance(candidate, list) or len(candidate) != 2:
            continue
        rank, cpe = candidate
        if not cpe:
            continue
        parts = cpe.split(":")
        vendor = parts[3] if len(parts) > 3 else None
        product = parts[4] if len(parts) > 4 else None
        if _is_placeholder_cpe(vendor, product):
            continue
        return cpe, rank

    return None, None


def guess_cpe(name, cpe_guesser_url):
    """
    Resolve a CPE for a software name using cpe-guesser, with fallback.

    First attempt: full cleaned tokens. If that fails, retry once with a
    leading isolated `lib` prefix stripped (never on the first attempt, to
    avoid breaking names like libreoffice).

    Returns (cpe, rank) or (None, None) if nothing usable was found.
    """
    tokens = clean_tokens(name)
    LOGGER.debug("guess_cpe: name=%r -> tokens=%s", name, tokens)
    cpe, rank = _query_cpe_guesser(cpe_guesser_url, tokens)
    if cpe:
        LOGGER.debug("guess_cpe: name=%r matched cpe=%s rank=%s", name, cpe, rank)
        return cpe, rank

    fallback_tokens = _strip_lib_prefix(tokens)
    if fallback_tokens != tokens:
        LOGGER.debug("guess_cpe: name=%r retrying without lib prefix -> tokens=%s", name, fallback_tokens)
        cpe, rank = _query_cpe_guesser(cpe_guesser_url, fallback_tokens)
        if cpe:
            LOGGER.debug("guess_cpe: name=%r matched (fallback) cpe=%s rank=%s", name, cpe, rank)
            return cpe, rank

    LOGGER.debug("guess_cpe: name=%r -> no match", name)
    return None, None


_SEMVER_RE = re.compile(r"^\d+(\.\d+)*$")


def _parse_semver(value):
    """Parse a dotted numeric version ("3.0.22") into a tuple of ints, or None."""
    if not value or not _SEMVER_RE.match(value):
        return None
    return tuple(int(part) for part in value.split("."))


def _compare_versions(a, b):
    """Compare two version tuples of possibly different lengths (1.2 vs 1.2.0)."""
    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))
    b = b + (0,) * (length - len(b))
    return (a > b) - (a < b)


def _semver_range_matches(installed, version_range):
    """
    Check whether `installed` (a parsed semver tuple) falls inside a single
    affected[].versions[] entry, itself semver (version + lessThan/lessThanOrEqual).

    version_range["version"] is the range's lower bound (inclusive), unless
    it is the sentinel "0" with no upper bound, which cve-search/CVE records
    use to mean "all versions before the upper bound".
    """
    lower = _parse_semver(version_range.get("version"))
    if lower is None:
        return None

    if _compare_versions(installed, lower) < 0:
        return False

    if "lessThan" in version_range:
        upper = _parse_semver(version_range["lessThan"])
        if upper is None:
            return None
        return _compare_versions(installed, upper) < 0

    if "lessThanOrEqual" in version_range:
        upper = _parse_semver(version_range["lessThanOrEqual"])
        if upper is None:
            return None
        return _compare_versions(installed, upper) <= 0

    # No upper bound given: the range is just this exact version.
    return _compare_versions(installed, lower) == 0


VERSION_MATCH_STATUS_MATCHED = "matched"
VERSION_MATCH_STATUS_UNKNOWN = "unknown"
VERSION_MATCH_STATUS_EXCLUDED = "excluded"


def _cve_version_match_status(record, installed_version):
    """
    Check whether `installed_version` is covered by the CVE record's
    containers.cna.affected[].versions[] ranges.

    A range is only evaluated if its version/lessThan/lessThanOrEqual values
    actually parse as dotted-numeric (see _parse_semver) — the declared
    versionType is not trusted as a gate: in practice it's often missing or
    set to "custom" even when the value is a plain numeric version (e.g.
    Notepad++ CVEs report {"version": "8.9.3"} with no versionType at all).
    Ranges that don't parse (git commit hashes, free text, ...) are simply
    skipped rather than compared.

    Returns one of:
      - "matched": a numeric range was checked and covers the installed version
      - "excluded": numeric ranges were checked and none covers it
      - "unknown": no comparable (numeric) range was found, or the installed
        version itself isn't parseable — the CVE is kept rather than
        silently dropped, to avoid turning an unknown into a false negative
    """
    installed = _parse_semver(installed_version)
    if installed is None:
        return VERSION_MATCH_STATUS_UNKNOWN

    affected = record.get("containers", {}).get("cna", {}).get("affected") or []
    saw_any_comparable_range = False
    for entry in affected:
        for version_range in entry.get("versions", []) or []:
            if version_range.get("status") != "affected":
                continue
            result = _semver_range_matches(installed, version_range)
            if result is None:
                continue
            saw_any_comparable_range = True
            if result:
                return VERSION_MATCH_STATUS_MATCHED

    if not saw_any_comparable_range:
        return VERSION_MATCH_STATUS_UNKNOWN

    return VERSION_MATCH_STATUS_EXCLUDED


def _cve_affects_version(record, installed_version):
    """True unless the CVE's semver ranges are known and exclude installed_version."""
    return _cve_version_match_status(record, installed_version) != VERSION_MATCH_STATUS_EXCLUDED


def _extract_cvss(record):
    """Best CVSS baseScore found in cna and adp metrics, preferring v3.1 > v3.0 > v2.0."""
    containers = record.get("containers", {})
    metric_groups = []

    cna = containers.get("cna", {})
    metric_groups.extend(cna.get("metrics", []) or [])

    for adp in containers.get("adp", []) or []:
        metric_groups.extend(adp.get("metrics", []) or [])

    for version_key in ("cvssV3_1", "cvssV3_0", "cvssV2_0"):
        for metrics in metric_groups:
            metric = metrics.get(version_key)
            if metric and metric.get("baseScore") is not None:
                return metric["baseScore"]

    return None


def _parse_published_date(raw_date):
    """
    Parse cveMetadata.datePublished into a date, or None.

    The CVE v5 record gives a full ISO 8601 timestamp (e.g.
    "2026-08-28T17:45:35.161Z"), not a bare date, so CveReport.published_date
    (a DateField) needs just the date part.
    """
    if not raw_date:
        return None
    try:
        return date.fromisoformat(raw_date[:10])
    except ValueError:
        LOGGER.warning("Could not parse published date %r", raw_date)
        return None


def _parse_vulnerability_lookup_response(payload, installed_version=None):
    """
    Deduplicate CVE records from a Vulnerability-Lookup /search response.

    payload["results"] maps source name (nvd, cvelistv5, ...) to a list of
    [cve_id_lowercase, record] pairs. The same CVE commonly appears in
    several sources, dedup by record["cveMetadata"]["cveId"]. Records whose
    cveMetadata.state is "REJECTED" (withdrawn/replaced by their CNA) are
    skipped entirely.

    When installed_version is given, records whose semver affected[] ranges
    are known and don't cover that version are skipped (see
    _cve_version_match_status for what "known" means). Each kept record
    carries a "version_match" status: "matched" if a semver range confirmed
    the installed version is affected, "unknown" if no comparable range was
    found (kept by default, not verified).
    """
    seen = {}
    results = payload.get("results", {}) or {}
    for _source, entries in results.items():
        for entry in entries or []:
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            _cve_id_lower, record = entry
            metadata = record.get("cveMetadata", {})
            cve_id = metadata.get("cveId")
            if not cve_id or cve_id in seen:
                continue
            if metadata.get("state") == "REJECTED":
                LOGGER.debug("%s is REJECTED, skipping", cve_id)
                continue

            version_match = VERSION_MATCH_STATUS_UNKNOWN
            if installed_version:
                version_match = _cve_version_match_status(record, installed_version)
                if version_match == VERSION_MATCH_STATUS_EXCLUDED:
                    LOGGER.debug(
                        "%s does not affect installed version %s, skipping",
                        cve_id,
                        installed_version,
                    )
                    continue

            seen[cve_id] = {
                "cve_id": cve_id,
                "cvss_score": _extract_cvss(record),
                "published_date": _parse_published_date(metadata.get("datePublished")),
                "version_match": version_match,
            }
    return list(seen.values())


MAX_FETCH_PAGES = 50


def fetch_cves(vulnerability_lookup_url, vendor, product, installed_version=None):
    """
    Fetch and paginate all CVEs for a vendor/product pair from Vulnerability-Lookup.

    Returns a list of dicts {cve_id, cvss_score, published_date} on success
    (an empty list is a valid, successful result: no CVE applies). Returns
    None if the fetch could not complete (no URL configured, network error,
    non-200 response) — callers must distinguish this from "zero CVEs" so a
    transient failure never gets mistaken for "software is no longer
    affected by anything" and wipes out existing CveReport rows.

    When installed_version is given, CVEs whose affected[] semver ranges are
    known and exclude that version are filtered out (see _cve_affects_version).
    CVEs with no parseable semver range are kept rather than dropped, to
    avoid turning an unknown range into a silent false negative.

    Pagination is capped at MAX_FETCH_PAGES: a very popular product (e.g.
    Firefox has 6830+ CVEs at page_size=10, i.e. 683+ sequential requests)
    would otherwise take several minutes per software and stall the whole
    enrichment run. Vulnerability-Lookup returns results newest-first, so
    capping pages only drops the oldest, least actionable CVEs — the most
    recent ones (the ones that matter for triage) are always fetched.
    """
    if not vulnerability_lookup_url:
        return None

    all_records = {}
    page = 1
    while True:
        if page > MAX_FETCH_PAGES:
            LOGGER.warning(
                "Vulnerability-Lookup pagination capped at %d pages for %s/%s, "
                "older CVEs were not fetched",
                MAX_FETCH_PAGES,
                vendor,
                product,
            )
            break

        url = f"{vulnerability_lookup_url.rstrip('/')}/search/{vendor}/{product}"
        try:
            resp = requests.get(url, params={"page": page}, timeout=10)
            LOGGER.debug(
                "Vulnerability-Lookup GET %s?page=%d -> status=%d body=%s",
                url,
                page,
                resp.status_code,
                resp.text[:500],
            )
            if resp.status_code != 200:
                if page == 1:
                    return None
                break
            payload = resp.json()
        except Exception:
            LOGGER.exception(
                "Vulnerability-Lookup query failed for %s/%s (page %d)",
                vendor,
                product,
                page,
            )
            return None if page == 1 else list(all_records.values())

        page_records = _parse_vulnerability_lookup_response(payload, installed_version)
        LOGGER.debug(
            "Vulnerability-Lookup page %d for %s/%s: %d records kept (total_count=%s)",
            page,
            vendor,
            product,
            len(page_records),
            payload.get("total_count"),
        )
        for record in page_records:
            all_records[record["cve_id"]] = record

        total_count = payload.get("total_count", 0)
        page_size = payload.get("page_size", len(all_records) or 1)
        if page * page_size >= total_count:
            break
        page += 1

    return list(all_records.values())


def _cache_still_valid(timestamp, cache_validity_hours):
    if timestamp is None:
        return False
    return timestamp >= timezone.now() - timedelta(hours=cache_validity_hours)


def _cpe_to_vendor_product(cpe):
    parts = cpe.split(":")
    if len(parts) <= 4:
        return None, None
    return parts[3], parts[4]


def installed_version_display(software):
    """major_version.minor_version when both are set, else the raw version."""
    if software.major_version is not None and software.minor_version is not None:
        return f"{software.major_version}.{software.minor_version}"
    return software.version


def enrich_software(software):
    """
    Resolve a CPE for `software` and, if the match is confident enough,
    fetch and persist its CVEs.

    Must never re-decide a CpeMatch that is REJECTED (any source) or
    CONFIRMED with source == manual — those are human decisions, frozen
    forever. The caller (CveEnrichment task) is responsible for filtering
    those out before calling this function.

    A CpeMatch that is already CONFIRMED (regardless of source) never has
    its CPE re-guessed here either — cpe-guesser's rank for the same input
    can vary between calls, so re-guessing could flip an already-confirmed
    match back to pending_review and silently drop its CVE history. Once
    confirmed, only fetch_and_store_cves() (with its own TTL) keeps running
    against that fixed CPE.
    """
    from .models import CpeMatch

    config = get_cve_config()
    cache_validity_hours = config["cache_validity_hours"]

    cpe_match = getattr(software, "cpe_match", None)

    if cpe_match and cpe_match.status == CpeMatch.STATUS_CONFIRMED:
        fetch_and_store_cves(software, cpe_match.cpe, config=config)
        return

    if cpe_match and _cache_still_valid(cpe_match.updated_at, cache_validity_hours):
        LOGGER.info("CPE match cache hit for software %s", software.id)
        return

    cpe, rank = guess_cpe(software.name, config["cpe_guesser_url"])

    if not cpe:
        LOGGER.info("No CPE match for software %s (%r)", software.id, software.name)
        CpeMatch.objects.update_or_create(
            software=software,
            defaults={
                "cpe": None,
                "cpe_rank": None,
                "source": CpeMatch.SOURCE_AUTO,
                "status": CpeMatch.STATUS_NO_MATCH,
            },
        )
        return

    min_confidence_rank = config["min_confidence_rank"]
    is_confident = rank is not None and rank >= min_confidence_rank
    status = CpeMatch.STATUS_CONFIRMED if is_confident else CpeMatch.STATUS_PENDING_REVIEW
    LOGGER.info(
        "CPE match for software %s (%r): cpe=%s rank=%s status=%s (threshold=%s)",
        software.id,
        software.name,
        cpe,
        rank,
        status,
        min_confidence_rank,
    )

    cpe_match, _ = CpeMatch.objects.update_or_create(
        software=software,
        defaults={
            "cpe": cpe,
            "cpe_rank": rank,
            "source": CpeMatch.SOURCE_AUTO,
            "status": status,
        },
    )

    if status != CpeMatch.STATUS_CONFIRMED:
        return

    fetch_and_store_cves(software, cpe, config=config)


def fetch_and_store_cves(software, cpe, config=None):
    """
    Fetch CVEs for a confirmed CPE and persist them as CveReport rows.

    Only ever called for a software whose CpeMatch.status is CONFIRMED.
    """
    from .models import CveReport

    config = config or get_cve_config()
    cache_validity_hours = config["cache_validity_hours"]

    latest_fetch = (
        CveReport.objects.filter(software=software)
        .order_by("-fetched_at")
        .values_list("fetched_at", flat=True)
        .first()
    )
    if _cache_still_valid(latest_fetch, cache_validity_hours):
        LOGGER.info("CVE report cache hit for software %s", software.id)
        return

    vendor, product = _cpe_to_vendor_product(cpe)
    if not vendor or not product:
        return

    installed_version = installed_version_display(software)
    records = fetch_cves(
        config["vulnerability_lookup_url"], vendor, product, installed_version
    )
    if records is None:
        LOGGER.warning(
            "Vulnerability-Lookup fetch failed for software %s, keeping existing CVE reports as-is",
            software.id,
        )
        return

    # CVEs with no CVSS score can't be prioritized or triaged, so they are
    # not persisted at all — filtering here also lets the stale-cleanup pass
    # below remove any such entry already stored from before this change.
    records = [record for record in records if record["cvss_score"] is not None]

    for record in records:
        CveReport.objects.update_or_create(
            software=software,
            cve_id=record["cve_id"],
            defaults={
                "cvss_score": record["cvss_score"],
                "published_date": record["published_date"],
                "version_match": record.get("version_match", CveReport.VERSION_MATCH_UNKNOWN),
            },
        )

    # Drop reports that no longer apply (software updated past the affected
    # range, CPE corrected to a different product, CVE record retracted...).
    # Only reached on a successful fetch, never on a failed one, so a
    # transient outage can't be mistaken for "nothing applies anymore".
    current_cve_ids = {record["cve_id"] for record in records}
    stale = CveReport.objects.filter(software=software).exclude(cve_id__in=current_cve_ids)
    stale_count = stale.count()
    if stale_count:
        LOGGER.info(
            "Removing %d stale CVE report(s) for software %s no longer affected",
            stale_count,
            software.id,
        )
        stale.delete()
