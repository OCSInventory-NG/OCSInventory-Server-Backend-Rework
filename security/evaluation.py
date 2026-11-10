"""
An identity checked once against the local data: its findings are then copied
to every machine that has it installed (security.scan).

Linux: the OSV ranges of the package's ecosystem, compared by OCS with dpkg
or rpm rules. Ubuntu: the Ubuntu Pro ecosystem is read too after the end of
standard support, or for a package of an Ubuntu Pro repository; a standard
fix comes first. Windows and macOS: the NVD matches of the product and its
aliases, within the loaded years.
"""

from collections import defaultdict, namedtuple
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from inventory.software.models import DistroRelease
from inventory.software_identity.models import CpeAlias, PackageOrigin
from security import config as security_config
from security.cvss import base_score, normalize_rating
from security.models import (
    CHANNEL_STANDARD,
    CHANNEL_UBUNTU_PRO,
    METHOD_OSV,
    OSV_SOURCES,
    SOURCE_NVD,
    EpssScore,
    Evaluation,
    Finding,
    KevEntry,
    NvdCve,
    NvdMatch,
    OsvAdvisoryCve,
    OsvAffected,
    Vulnerability,
)
from security.sources import nvd, osv
from security.sync import (
    FRESH,
    NEVER_LOADED,
    data_version,
    source_state,
    source_syncs,
)
from security.kernel import is_noise
from security.versions import comparator, module_streams, rpm_compare, same_stream

EvaluationKey = namedtuple(
    "EvaluationKey", "scheme product version platform_key extended"
)

# Rows per INSERT
WRITE_BATCH = 1000
# Debian urgencies not reported: no impact for Debian, or not triaged yet.
# They made most of a Debian machine's findings, all of them noise.
MINOR_RATINGS = ("unimportant", "not yet assigned")
# Identity statuses whose products are checked, per scheme
COVERED = {"purl": ("matched",), "cpe": ("matched", "validated")}
# The full scan runs weekly: an evaluation made with older data still counts
# as checked while the newer data waits less than this for it
RESCAN_GRACE = timedelta(days=8)


def is_covered(status, scheme):
    return status in COVERED.get(scheme, ())


class Context:
    """What the evaluations and the coverage read once: sources, releases, aliases."""

    def __init__(self, now=None):
        self.now = now or timezone.now()
        self.settings = security_config.current()
        self.syncs = source_syncs()
        self.states = {
            source: source_state(sync, self.now) for source, sync in self.syncs.items()
        }
        self.ecosystems = {
            ecosystem
            for source in OSV_SOURCES
            for ecosystem in (self.syncs[source].details or {}).get("ecosystems", [])
        }
        self.support_end = {}
        # End of every security support, per (base, version)
        self.full_support_end = {}
        for base, version, standard, full in DistroRelease.objects.values_list(
            "base", "version", "standard_support_end", "support_end"
        ):
            self.support_end[(base, version)] = standard
            self.full_support_end[(base, version)] = full
        self.extended_origins = {
            name.strip().lower()
            for name in PackageOrigin.objects.filter(extended=True).values_list(
                "name", flat=True
            )
        }
        self.aliases = defaultdict(set)
        for product, alias in CpeAlias.objects.values_list("product", "alias"):
            self.aliases[product].add(alias)
        self.window = nvd.window(self.settings.nvd_years, self.now)

    # Keys and sources

    def key(self, scheme, product, version, platform_key, origin):
        """The evaluation key of a covered identity, None when no source handles it."""
        if scheme == "purl":
            standard, _ = osv.ecosystems(product, platform_key)
            if standard is None or osv.source_of(product) is None:
                return None
            extended = (origin or "").strip().lower() in self.extended_origins
            return EvaluationKey(scheme, product, version, platform_key, extended)
        if scheme == "cpe":
            return EvaluationKey(scheme, product, version, platform_key or "", False)
        return None

    def source(self, key):
        return osv.source_of(key.product) if key.scheme == "purl" else SOURCE_NVD

    def ecosystems_of(self, key):
        """OSV ecosystems read for a Linux key: standard, then Ubuntu Pro."""
        standard, pro = osv.ecosystems(key.product, key.platform_key)
        if pro and (key.extended or self.past_standard_support(key.platform_key)):
            return [standard, pro]
        return [standard]

    def past_standard_support(self, platform_key):
        base, _, release = platform_key.partition(":")
        end = self.support_end.get((base, release))
        return end is not None and self.now.date() > end

    def past_support(self, platform_key):
        """The release's security support ended: its date, else None."""
        base, _, release = platform_key.partition(":")
        end = self.full_support_end.get((base, release))
        return end if end is not None and self.now.date() > end else None

    def tracked(self, key):
        """Whether the source still publishes advisories for the key's release."""
        if key.scheme != "purl":
            return True
        return any(eco in self.ecosystems for eco in self.ecosystems_of(key))

    def up_to_date(self, key, evaluation_sources):
        """An evaluation made with the current data of its source."""
        source = self.source(key)
        version = data_version(self.syncs[source])
        if evaluation_sources is None or version is None:
            return False
        return evaluation_sources.get(source) == version.isoformat()

    def checked(self, key, evaluation_sources):
        """
        An evaluation that still stands: made with the current data, or with
        older data while the full scan has had less than RESCAN_GRACE to
        bring it up to date.
        """
        if self.up_to_date(key, evaluation_sources):
            return True
        source = self.source(key)
        version = data_version(self.syncs[source])
        if not (evaluation_sources or {}).get(source) or version is None:
            return False
        return self.now - version <= RESCAN_GRACE

    def loaded(self, key):
        return self.states[self.source(key)] != NEVER_LOADED

    def fresh(self, key):
        return self.states[self.source(key)] == FRESH


# OSV ranges


def _range_intervals(events, compare):
    """[(start, end, kind)] of a range, end None when open."""
    order = {"introduced": 0, "fixed": 1, "last_affected": 1, "limit": 1}

    def version_of(event):
        return next(iter(event.values()), "")

    def sort_key(event):
        kind = next(iter(event), "")
        value = version_of(event)
        return (
            0 if (kind == "introduced" and value == "0") else 1,
            value,
            order.get(kind, 2),
        )

    from functools import cmp_to_key

    def compare_events(a, b):
        ka, kb = sort_key(a), sort_key(b)
        if ka[0] != kb[0]:
            return ka[0] - kb[0]
        result = compare(ka[1], kb[1]) if ka[0] else 0
        return result or (ka[2] - kb[2])

    intervals, start = [], None
    for event in sorted(events, key=cmp_to_key(compare_events)):
        kind = next(iter(event), "")
        value = version_of(event)
        if kind == "introduced":
            if start is None:
                start = value
        elif kind in ("fixed", "last_affected", "limit") and start is not None:
            intervals.append((start, value, kind))
            start = None
    if start is not None:
        intervals.append((start, None, None))
    return intervals


def affected_by(ranges, versions, installed, compare):
    """(affected, fixed version, range in words) of an installed version."""
    words = ", ".join(
        f"{kind.replace('_', ' ')} {value}"
        for events in ranges
        for event in events
        for kind, value in event.items()
    )
    if installed in (versions or []):
        return True, "", words
    for events in ranges:
        for start, end, kind in _range_intervals(events, compare):
            if start != "0" and compare(installed, start) < 0:
                continue
            if end is None:
                return True, "", words
            result = compare(installed, end)
            if (kind == "last_affected" and result <= 0) or (
                kind in ("fixed", "limit") and result < 0
            ):
                return True, end if kind == "fixed" else "", words
    return False, "", words


def evaluate_osv(key, context):
    """Findings of a Linux key: one per CVE of each affecting advisory."""
    ecosystems = context.ecosystems_of(key)
    compare = comparator(ecosystems[0])
    source_name = osv.query_name(key.product)
    family = key.product[4:].split("/")[0]
    rows = (
        OsvAffected.objects.filter(
            ecosystem__in=ecosystems,
            package=source_name,
            advisory__detection=True,
            advisory__withdrawn=False,
        )
        .select_related("advisory")
        .order_by("advisory__advisory_id", "id")
    )
    per_advisory = defaultdict(lambda: defaultdict(list))
    advisories = {}
    for row in rows:
        advisories[row.advisory_id] = row.advisory
        per_advisory[row.advisory_id][row.ecosystem].append(row)
    findings = []
    modules = compare is rpm_compare
    for advisory_id, by_ecosystem in per_advisory.items():
        advisory = advisories[advisory_id]
        streams = module_streams(advisory.summary) if modules else {}
        results = {}
        for ecosystem, entries in by_ecosystem.items():
            affected, fixed, words, urgency = False, "", "", ""
            for entry in entries:
                hit, entry_fixed, entry_words = affected_by(
                    entry.ranges, entry.versions, key.version, compare
                )
                words = words or entry_words
                urgency = urgency or entry.urgency
                if (
                    hit
                    and modules
                    and not same_stream(key.version, entry_fixed, source_name, streams)
                ):
                    # The fix of another module stream: not for this version
                    continue
                if hit:
                    affected, fixed = True, fixed or entry_fixed
            results[ecosystem] = (affected, fixed, words, urgency)
        # Fixed in one of the ecosystems read: the installed version has the fix
        if not all(result[0] for result in results.values()):
            continue
        standard = results.get(ecosystems[0])
        pro = results.get(ecosystems[1]) if len(ecosystems) > 1 else None
        if standard and standard[1]:
            fixed, channel, words, urgency = (
                standard[1],
                CHANNEL_STANDARD,
                standard[2],
                standard[3],
            )
        elif pro and pro[1]:
            fixed, channel, words, urgency = pro[1], CHANNEL_UBUNTU_PRO, pro[2], pro[3]
        else:
            first = standard or pro
            fixed, channel, words, urgency = "", CHANNEL_STANDARD, first[2], first[3]
        rating = normalize_rating(advisory.rating or urgency)
        if rating in MINOR_RATINGS:
            continue
        if is_noise(source_name, family, fixed=fixed):
            continue
        for vuln_id in advisory.cves or [advisory.advisory_id]:
            findings.append(
                {
                    "vuln_id": vuln_id,
                    "advisory_id": advisory.advisory_id,
                    "fixed_version": fixed,
                    "fix_channel": channel,
                    "affected_range": words,
                    "method": METHOD_OSV,
                    "uncertain": False,
                    "rating": rating,
                    "summary": advisory.summary,
                    "published": advisory.published,
                    "vector": advisory.cvss_vector,
                    "url": osv.advisory_url(advisory.advisory_id),
                }
            )
    return findings


class NvdProducts:
    """The CVE matches of CPE products and their aliases, read once per product."""

    def __init__(self, context):
        self.context = context
        self.cache = {}

    def matches(self, product):
        if product not in self.cache:
            names = {product} | self.context.aliases.get(product, set())
            per_cve = defaultdict(list)
            for cve_id, criteria, bounds, conditional in NvdMatch.objects.filter(
                vendor_product__in=names,
                cve__full=True,
                cve__rejected=False,
                cve__year__in=self.context.window,
            ).values_list("cve__cve_id", "criteria", "bounds", "conditional"):
                per_cve[cve_id].append(
                    {"criteria": criteria, "bounds": bounds, "conditional": conditional}
                )
            if len(self.cache) > 200:
                self.cache.clear()
            self.cache[product] = per_cve
        return self.cache[product]


def evaluate_nvd(key, products):
    findings = []
    for cve_id, matches in sorted(products.matches(key.product).items()):
        result = nvd.evaluate(matches, key.version, key.platform_key)
        if result is None:
            continue
        findings.append(
            {
                "vuln_id": cve_id,
                "advisory_id": cve_id,
                "fixed_version": result["fixed_version"],
                "fix_channel": CHANNEL_STANDARD,
                "affected_range": result["affected_range"],
                "method": result["method"],
                "uncertain": result["uncertain"],
                "rating": "",
                "summary": "",
                "published": None,
                "vector": "",
                "url": nvd.cve_url(cve_id),
            }
        )
    return findings


def _vulnerabilities(findings):
    """{vuln_id: Vulnerability}, created with what the advisories tell."""
    ids = {finding["vuln_id"] for finding in findings}
    existing = {v.vuln_id: v for v in Vulnerability.objects.filter(vuln_id__in=ids)}
    created = []
    for finding in findings:
        if finding["vuln_id"] in existing:
            continue
        vulnerability = Vulnerability(
            vuln_id=finding["vuln_id"][:128],
            summary=finding["summary"],
            published=finding["published"],
            cvss_vector=finding["vector"][:255],
            distro_rating=finding["rating"][:32],
            url=finding["url"][:255],
        )
        existing[finding["vuln_id"]] = vulnerability
        created.append(vulnerability)
    if created:
        Vulnerability.objects.bulk_create(created, batch_size=WRITE_BATCH)
        for vulnerability in Vulnerability.objects.filter(
            vuln_id__in=[v.vuln_id for v in created]
        ):
            existing[vulnerability.vuln_id] = vulnerability
    return existing


def store(key, findings, context):
    """Replaces the key's evaluation and findings. Returns the evaluation."""
    source = context.source(key)
    version = data_version(context.syncs[source])
    with transaction.atomic():
        evaluation, _ = Evaluation.objects.update_or_create(
            scheme=key.scheme,
            product=key.product,
            version=key.version,
            platform_key=key.platform_key,
            extended=key.extended,
            defaults={
                "evaluated_at": context.now,
                "sources": {source: version.isoformat() if version else ""},
            },
        )
        vulnerabilities = _vulnerabilities(findings)
        evaluation.findings.all().delete()
        unique = {}
        for finding in findings:
            unique.setdefault(finding["vuln_id"], finding)
        Finding.objects.bulk_create(
            (
                Finding(
                    evaluation=evaluation,
                    vulnerability=vulnerabilities[vuln_id],
                    advisory_id=finding["advisory_id"][:128],
                    fixed_version=finding["fixed_version"][:255],
                    fix_channel=finding["fix_channel"],
                    affected_range=finding["affected_range"][:255],
                    method=finding["method"],
                    uncertain=finding["uncertain"],
                    rating=(finding["rating"] or "")[:32],
                )
                for vuln_id, finding in unique.items()
            ),
            batch_size=WRITE_BATCH,
        )
    return evaluation


def evaluate(key, context, products=None):
    """Evaluates and stores a key."""
    if key.scheme == "purl":
        findings = evaluate_osv(key, context)
    else:
        findings = evaluate_nvd(key, products or NvdProducts(context))
    return store(key, findings, context)


# What the priority reads, refreshed after each synchronization and scan


def _cvss_version(vector):
    prefix = (vector or "").split("/")[0]
    return prefix.split(":", 1)[1] if prefix.startswith("CVSS:") else ""


def refresh_vulnerabilities(ids=None):
    """
    Retained score (CVSS 3.x, else 4.0; the NVD first, then the advisory),
    KEV, EPSS, NVD summary, of the given vulnerability ids (all when None).
    """
    vulnerabilities = Vulnerability.objects.all()
    if ids is not None:
        vulnerabilities = vulnerabilities.filter(id__in=list(ids))
    batch = 1000
    pending = list(vulnerabilities.order_by("id"))
    for start in range(0, len(pending), batch):
        chunk = pending[start : start + batch]
        names = [v.vuln_id for v in chunk]
        cves = {cve.cve_id: cve for cve in NvdCve.objects.filter(cve_id__in=names)}
        kev = {entry.cve: entry for entry in KevEntry.objects.filter(cve__in=names)}
        epss = {score.cve: score for score in EpssScore.objects.filter(cve__in=names)}
        advisory_vectors = {}
        for cve, vector in OsvAdvisoryCve.objects.filter(cve__in=names).values_list(
            "cve", "advisory__cvss_vector"
        ):
            if vector and (cve not in advisory_vectors or vector.startswith("CVSS:3")):
                advisory_vectors[cve] = vector
        for vulnerability in chunk:
            name = vulnerability.vuln_id
            cve = cves.get(name)
            vector, score = "", None
            if cve and cve.cvss3_vector:
                vector, score = cve.cvss3_vector, cve.cvss3_score
            elif cve and cve.cvss4_vector:
                vector, score = cve.cvss4_vector, cve.cvss4_score
            elif advisory_vectors.get(name) or vulnerability.cvss_vector:
                vector = advisory_vectors.get(name) or vulnerability.cvss_vector
                # A 4.0 vector of an advisory has no score computed here
                score = base_score(vector)
            vulnerability.cvss_vector = vector[:255]
            vulnerability.cvss_version = _cvss_version(vector)
            vulnerability.cvss_score = score
            if cve:
                vulnerability.summary = cve.description or vulnerability.summary
                vulnerability.published = cve.published or vulnerability.published
                vulnerability.modified = cve.modified
            entry = kev.get(name)
            vulnerability.kev = entry is not None
            vulnerability.kev_date_added = entry.date_added if entry else None
            score_entry = epss.get(name)
            vulnerability.epss = score_entry.score if score_entry else None
            vulnerability.epss_percentile = (
                score_entry.percentile if score_entry else None
            )
        Vulnerability.objects.bulk_update(
            chunk,
            [
                "cvss_vector",
                "cvss_version",
                "cvss_score",
                "summary",
                "published",
                "modified",
                "kev",
                "kev_date_added",
                "epss",
                "epss_percentile",
            ],
        )
