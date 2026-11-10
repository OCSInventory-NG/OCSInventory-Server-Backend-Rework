"""
The scan: evaluates the identities whose evaluation is missing or older than
their source's data, then copies the findings to the machines as exposures,
and closes the exposures that no longer hold.

Every installation goes through the same tests (installation_state); the
first that fails gives the state shown. Only a checked installation can close
an exposure: losing data never closes anything.
"""

import logging
import os
import resource
from collections import Counter, defaultdict

from asset.inventory_base.models import InventoryBase
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from inventory.software.models import AssetPlatform, SoftwareDictionary
from inventory.software_identity.models import SoftwareIdentity
from security.evaluation import (
    Context,
    EvaluationKey,
    NvdProducts,
    evaluate,
    is_covered,
    refresh_vulnerabilities,
)
from security.exclusions import active_exclusions
from security.kernel import is_kernel, is_noise, is_running_kernel
from security.models import (
    RESOLUTION_FIXED,
    RESOLUTION_IDENTITY_CHANGED,
    RESOLUTION_OUT_OF_WINDOW,
    RESOLUTION_UNINSTALLED,
    RESOLUTION_WITHDRAWN,
    Evaluation,
    Exposure,
    Finding,
    ScanState,
    Vulnerability,
)
from security.sources import nvd, osv
from security.sync import locked

logger = logging.getLogger(__name__)

ASSET_BATCH = 200
# Rows per INSERT or UPDATE
WRITE_BATCH = 1000


def memory_mb():
    """Resident memory of this process in MB (Linux), else its peak."""
    try:
        with open("/proc/self/statm") as statm:
            pages = int(statm.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") // 2**20
    except (OSError, ValueError, IndexError):
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


# Installation states, in the order of the tests
EXCLUDED = "excluded"
KERNEL_NOT_RUNNING = "kernel_not_running"
NO_IDENTITY = "no_identity"
THIRD_PARTY = "third_party"
NO_ORIGIN = "no_origin"
NOT_SUPPORTED = "not_supported"
NOT_HANDLED = "not_handled"
RELEASE_NOT_TRACKED = "release_not_tracked"
SOURCE_NEVER_LOADED = "source_never_loaded"
STALE = "stale"
PENDING = "pending"
CHECKED = "checked"
STATES = (
    EXCLUDED,
    KERNEL_NOT_RUNNING,
    NO_IDENTITY,
    THIRD_PARTY,
    NO_ORIGIN,
    NOT_SUPPORTED,
    NOT_HANDLED,
    RELEASE_NOT_TRACKED,
    SOURCE_NEVER_LOADED,
    STALE,
    PENDING,
    CHECKED,
)
# A Linux machine whose running kernel matches no installed package
HOST_KERNEL_UNVERIFIED = "host_kernel_unverified"


class Installations:
    """
    The software of a set of machines (all when asset_ids is None), with its
    identity, its evaluation key and its state, read once.
    """

    def __init__(self, context, asset_ids=None):
        self.context = context
        links = SoftwareDictionary.assets.through.objects.all()
        platforms = AssetPlatform.objects.all()
        if asset_ids is not None:
            links = links.filter(inventorybase_id__in=asset_ids)
            platforms = platforms.filter(asset_id__in=asset_ids)
        self.entries_of = defaultdict(list)
        for entry_id, asset_id in links.values_list(
            "softwaredictionary_id", "inventorybase_id"
        ):
            self.entries_of[asset_id].append(entry_id)
        entry_ids = {e for entries in self.entries_of.values() for e in entries}
        self.entries = {}
        for row in _chunked_values(
            SoftwareDictionary.objects.all(),
            entry_ids,
            "id",
            "name",
            "version",
            "platform_family",
            "platform_key",
            "package_origin",
        ):
            self.entries[row[0]] = row[1:]
        self.identities = {}
        for row in _chunked_values(
            SoftwareIdentity.objects.all(),
            entry_ids,
            "entry_id",
            "status",
            "reason",
            "scheme",
            "product",
            "version",
            field="entry_id",
        ):
            self.identities[row[0]] = row[1:]
        self.platforms = {
            asset_id: (family, key, running)
            for asset_id, family, key, running in platforms.values_list(
                "asset_id", "family", "key", "running_kernel"
            )
        }
        self.asset_ids = set(self.entries_of) | set(self.platforms)
        if asset_ids is not None:
            self.asset_ids = set(asset_ids)
        self.excluded_assets = active_exclusions(context.now).scan_wide_assets()
        self.keys = {}
        for entry_id in entry_ids:
            self.keys[entry_id] = self._key(entry_id)
        self.evaluations = {}

    def _key(self, entry_id):
        identity = self.identities.get(entry_id)
        if identity is None:
            return None
        status, _, scheme, product, version = identity
        if not is_covered(status, scheme):
            return None
        _, _, _, platform_key, origin = self.entries[entry_id]
        return self.context.key(scheme, product, version, platform_key or "", origin)

    def load_evaluations(self):
        """{key: (evaluation id, sources)} of the keys of these installations."""
        keys = {key for key in self.keys.values() if key is not None}
        products = {key.product for key in keys}
        self.evaluations = {}
        for start, chunk in _chunks(sorted(products)):
            for row in Evaluation.objects.filter(product__in=chunk).values_list(
                "id",
                "scheme",
                "product",
                "version",
                "platform_key",
                "extended",
                "sources",
            ):
                key = EvaluationKey(*row[1:6])
                if key in keys:
                    self.evaluations[key] = (row[0], row[6])
        return self.evaluations

    def source_package(self, entry_id):
        identity = self.identities.get(entry_id)
        if identity and identity[2] == "purl" and identity[3]:
            return osv.package_name(identity[3])
        return ""

    def counts(self, entry_id, asset_id):
        """Whether an installed entry counts for a machine: the kernel rule."""
        name, version, family, _, _ = self.entries[entry_id]
        source = self.source_package(entry_id)
        if not is_kernel(name, family, source):
            return True
        running = self.platforms.get(asset_id, ("", "", ""))[2]
        return is_running_kernel(name, version, family, running, source)

    def is_kernel(self, entry_id):
        name, _, family, _, _ = self.entries[entry_id]
        return is_kernel(name, family, self.source_package(entry_id))

    def state(self, entry_id, asset_id):
        """The state of an installation: the first test that fails."""
        if asset_id in self.excluded_assets:
            return EXCLUDED
        if not self.counts(entry_id, asset_id):
            return KERNEL_NOT_RUNNING
        identity = self.identities.get(entry_id)
        if identity is None or identity[0] in ("review", "none"):
            return NO_IDENTITY
        status, reason, scheme, _, _ = identity
        if status == "unsupported":
            return reason if reason in (THIRD_PARTY, NO_ORIGIN) else NOT_SUPPORTED
        if not is_covered(status, scheme):
            return NOT_SUPPORTED
        key = self.keys.get(entry_id)
        if key is None:
            return NOT_HANDLED
        context = self.context
        if not context.loaded(key):
            return SOURCE_NEVER_LOADED
        if not context.tracked(key):
            return RELEASE_NOT_TRACKED
        if not context.fresh(key):
            return STALE
        evaluation = self.evaluations.get(key)
        if evaluation is None or not context.checked(key, evaluation[1]):
            return PENDING
        return CHECKED

    def running_kernel_state(self, asset_id):
        """The state of a Linux machine's running kernel, or host unverified."""
        family = self.platforms.get(asset_id, ("", "", ""))[0]
        if family not in ("deb", "rpm"):
            return None
        states = [
            self.state(entry_id, asset_id)
            for entry_id in self.entries_of.get(asset_id, ())
            if self.is_kernel(entry_id) and self.counts(entry_id, asset_id)
        ]
        if not states:
            return HOST_KERNEL_UNVERIFIED
        # The least covered package of the running kernel gives its state
        unchecked = [state for state in states if state != CHECKED]
        return min(unchecked, key=STATES.index) if unchecked else CHECKED


def _chunks(values, size=900):
    values = list(values)
    for start in range(0, len(values), size):
        yield start, values[start : start + size]


def _chunked_values(queryset, ids, *fields, field="id"):
    for _, chunk in _chunks(sorted(ids)):
        yield from queryset.filter(**{f"{field}__in": chunk}).values_list(*fields)


class ScanService:
    """Evaluates the identities and keeps the exposures of the machines."""

    @classmethod
    def run(cls, asset_ids=None, now=None, progress=None, lock=True, memory=None):
        """
        Full scan (asset_ids None) or a scan of some machines. Returns counts.
        Takes the shared lock unless the caller holds it. Above
        SECURITY_SCAN_MEMORY_LIMIT_MB the scan stops between two batches:
        what is done stays done, the next run resumes.
        """
        if lock:
            with locked(now):
                return cls._run(asset_ids, now, progress, memory)
        return cls._run(asset_ids, now, progress, memory)

    @classmethod
    def incremental(cls, now=None, progress=None):
        """
        The machines inventoried since the last scan, and those whose software
        got a new identity (a catalog decision, a new origin).
        """
        now = now or timezone.now()
        state = ScanState.current()
        since = state.last_incremental_scan or state.last_full_scan
        assets = InventoryBase.objects.all()
        if since is not None:
            assets = assets.filter(
                Q(last_update__gte=since)
                | Q(platform__updated_at__gte=since)
                | Q(software_dictionary_entries__identity__updated_at__gte=since)
            )
        asset_ids = list(assets.values_list("id", flat=True).distinct())
        counts = cls.run(asset_ids=asset_ids, now=now, progress=progress)
        if not counts.get("stopped_memory"):
            ScanState.objects.filter(pk=state.pk).update(last_incremental_scan=now)
        return counts

    @classmethod
    def _run(cls, asset_ids, now, progress, memory=None):
        now = now or timezone.now()
        memory = memory or memory_mb
        limit = settings.SECURITY_SCAN_MEMORY_LIMIT_MB
        progress = progress or logger.info
        context = Context(now)
        counts = Counter()
        full = asset_ids is None
        if full:
            asset_ids = list(
                set(
                    SoftwareDictionary.assets.through.objects.values_list(
                        "inventorybase_id", flat=True
                    )
                )
                | set(
                    Exposure.objects.filter(closed_at__isnull=True).values_list(
                        "asset_id", flat=True
                    )
                )
            )
        asset_ids = sorted(set(asset_ids))
        progress(f"Vulnerability scan of {len(asset_ids)} machines")
        products = NvdProducts(context)
        touched = set()
        for start, batch in _chunks(asset_ids, ASSET_BATCH):
            used = memory()
            if used > limit:
                logger.warning("Vulnerability scan stopped: %s MB used", used)
                progress(f"Scan stopped, memory limit reached ({used} MB of {limit})")
                counts["stopped_memory"] = 1
                refresh_vulnerabilities(touched)
                return dict(counts)
            installations = Installations(context, batch)
            cls._evaluate(installations, context, products, counts)
            installations.load_evaluations()
            touched |= cls._expose(installations, batch, counts)
            progress(
                f"Machines {start + 1} to {start + len(batch)} of {len(asset_ids)}:"
                f" {counts['evaluated']} identities evaluated,"
                f" {counts['opened']} exposures opened, {counts['closed']} closed"
            )
        if full:
            cls._cleanup()
            refresh_vulnerabilities()
            state = ScanState.current()
            ScanState.objects.filter(pk=state.pk).update(
                last_full_scan=now, last_incremental_scan=now
            )
        else:
            refresh_vulnerabilities(touched)
        return dict(counts)

    @staticmethod
    def _evaluate(installations, context, products, counts):
        """Evaluates the keys of the batch that are missing or out of date."""
        evaluations = installations.load_evaluations()
        keys = sorted(
            {key for key in installations.keys.values() if key is not None},
            key=lambda key: (key.scheme, key.product, key.version),
        )
        for key in keys:
            if not context.loaded(key):
                continue
            if key.scheme == "purl" and not context.tracked(key):
                continue
            current = evaluations.get(key)
            if current is not None and context.up_to_date(key, current[1]):
                continue
            try:
                evaluate(key, context, products)
            except Exception:
                logger.exception("Evaluation failed for %s", key)
                counts["evaluation_failed"] += 1
                continue
            counts["evaluated"] += 1

    @classmethod
    def _expose(cls, installations, asset_ids, counts):
        """Opens, updates and closes the exposures of a batch of machines."""
        context = installations.context
        now = context.now
        evaluation_ids = [ev[0] for ev in installations.evaluations.values()]
        findings = defaultdict(list)
        for _, chunk in _chunks(evaluation_ids):
            for finding in Finding.objects.filter(evaluation_id__in=chunk).values(
                "evaluation_id",
                "vulnerability_id",
                "advisory_id",
                "fixed_version",
                "fix_channel",
                "method",
                "uncertain",
                "rating",
            ):
                findings[finding["evaluation_id"]].append(finding)

        touched = set()
        for asset_id in asset_ids:
            wanted = {}
            # (scheme, product): [(version, state, vulnerability ids)]
            installed = defaultdict(list)
            for entry_id in installations.entries_of.get(asset_id, ()):
                key = installations.keys.get(entry_id)
                if key is None or not installations.counts(entry_id, asset_id):
                    continue
                state = installations.state(entry_id, asset_id)
                evaluation = installations.evaluations.get(key)
                vulnerabilities = set()
                if evaluation is not None:
                    name, _, family, _, _ = installations.entries[entry_id]
                    kernel = installations.is_kernel(entry_id)
                    linux = key.scheme == "purl"
                    source = osv.query_name(key.product) if linux else ""
                    for finding in findings[evaluation[0]]:
                        # Kept by an evaluation made before the noise rule
                        if linux and is_noise(
                            source, family, kernel, finding["fixed_version"]
                        ):
                            continue
                        vulnerabilities.add(finding["vulnerability_id"])
                        wanted[
                            (key.scheme, key.product, finding["vulnerability_id"])
                        ] = {
                            **finding,
                            "entry_id": entry_id,
                            "software_name": (name or "")[:255],
                            "version": key.version,
                            "platform_family": family or "",
                            "kernel": kernel,
                        }
                installed[(key.scheme, key.product)].append(
                    (key.version, state, vulnerabilities)
                )
            touched |= {vulnerability for (_, _, vulnerability) in wanted}
            cls._apply(asset_id, wanted, installed, installations, now, counts)
        return touched

    @staticmethod
    def _kernel_duplicates(wanted, open_exposures):
        """
        The triples of a kernel vulnerability found through another kernel
        package of the machine (linux and linux-signed on Ubuntu): a machine
        runs one kernel, the vulnerability is exposed once. The one kept is
        the exposure already open, else one with a fix, else the first
        product.
        """
        per_vulnerability = defaultdict(list)
        for triple, data in wanted.items():
            if data["kernel"]:
                per_vulnerability[triple[2]].append(triple)
        duplicates = set()
        for triples in per_vulnerability.values():
            if len(triples) < 2:
                continue
            kept = min(
                triples,
                key=lambda triple: (
                    triple not in open_exposures,
                    not wanted[triple]["fixed_version"],
                    triple[1],
                ),
            )
            duplicates.update(triple for triple in triples if triple != kept)
        return duplicates

    @classmethod
    def _apply(cls, asset_id, wanted, installed, installations, now, counts):
        open_exposures = {
            (exposure.scheme, exposure.product, exposure.vulnerability_id): exposure
            for exposure in Exposure.objects.filter(
                asset_id=asset_id, closed_at__isnull=True
            )
        }
        duplicates = cls._kernel_duplicates(wanted, open_exposures)
        wanted = {
            triple: data for triple, data in wanted.items() if triple not in duplicates
        }
        # Copies of an exposure kept, not history: they go
        to_delete = [
            open_exposures.pop(triple).id
            for triple in duplicates
            if triple in open_exposures
        ]
        to_update, to_create, to_close = [], [], []
        for triple, data in wanted.items():
            exposure = open_exposures.get(triple)
            fields = {
                "entry_id": data["entry_id"],
                "software_name": data["software_name"],
                "version": data["version"][:128],
                "platform_family": data["platform_family"],
                "advisory_id": data["advisory_id"],
                "fixed_version": data["fixed_version"],
                "fix_channel": data["fix_channel"],
                "method": data["method"],
                "uncertain": data["uncertain"],
                "kernel": data["kernel"],
                "rating": data["rating"],
                "last_seen": now,
            }
            if exposure is None:
                to_create.append(
                    Exposure(
                        asset_id=asset_id,
                        scheme=triple[0],
                        product=triple[1],
                        vulnerability_id=triple[2],
                        first_seen=now,
                        **fields,
                    )
                )
            else:
                for name, value in fields.items():
                    setattr(exposure, name, value)
                to_update.append(exposure)
        names, products = None, None
        for triple, exposure in open_exposures.items():
            if triple in wanted:
                continue
            if names is None:
                names, products = cls._asset_software(installations, asset_id)
            resolution = cls._resolution(
                exposure, installed, names, products, installations
            )
            if resolution:
                exposure.closed_at = now
                exposure.resolution = resolution
                to_close.append(exposure)
        with transaction.atomic():
            for _, chunk in _chunks(to_delete):
                Exposure.objects.filter(id__in=chunk).delete()
            Exposure.objects.bulk_create(to_create, batch_size=WRITE_BATCH)
            Exposure.objects.bulk_update(
                to_update,
                [
                    "entry_id",
                    "software_name",
                    "version",
                    "platform_family",
                    "advisory_id",
                    "fixed_version",
                    "fix_channel",
                    "method",
                    "uncertain",
                    "kernel",
                    "rating",
                    "last_seen",
                ],
                batch_size=WRITE_BATCH,
            )
            Exposure.objects.bulk_update(
                to_close, ["closed_at", "resolution"], batch_size=WRITE_BATCH
            )
        counts["opened"] += len(to_create)
        counts["closed"] += len(to_close)
        if to_delete:
            counts["kernel_duplicates_removed"] += len(to_delete)
        for exposure in to_close:
            counts[f"closed_{exposure.resolution}"] += 1

    @staticmethod
    def _asset_software(installations, asset_id):
        """
        Names of the software installed, and {(scheme, product): kernels} of
        the identities not counted: kernels True when one of them is a kernel
        that is not running.
        """
        names, products = set(), {}
        for entry_id in installations.entries_of.get(asset_id, ()):
            name = installations.entries[entry_id][0]
            names.add(name)
            identity = installations.identities.get(entry_id)
            if identity is None:
                # Not identified yet: what it will be is unknown
                products[("", name)] = True
            elif identity[3]:
                product = (identity[2], identity[3])
                resting = not installations.counts(entry_id, asset_id)
                products[product] = products.get(product, False) or resting
        return names, products

    @staticmethod
    def _resolution(exposure, installed, names, products, installations):
        """
        Why an exposure no longer found is closed, "" to keep it open: the
        first resolution that applies, decided on checked installations only.
        """
        current = installed.get((exposure.scheme, exposure.product))
        if current:
            if any(state != CHECKED for _, state, _ in current):
                return ""
            if any(exposure.vulnerability_id in found for _, _, found in current):
                return ""
            if any(version != exposure.version for version, _, _ in current):
                return RESOLUTION_FIXED
            if exposure.scheme == "cpe" and _out_of_window(exposure, installations):
                return RESOLUTION_OUT_OF_WINDOW
            return RESOLUTION_WITHDRAWN
        if products.get(("", exposure.software_name)):
            return ""
        if products.get((exposure.scheme, exposure.product)):
            # A kernel no longer running and no running kernel of that product
            # checked (a container runs its host's kernel): nothing proves it
            return ""
        if (
            exposure.software_name not in names
            and (exposure.scheme, exposure.product) not in products
        ):
            return RESOLUTION_UNINSTALLED
        # The software is there, its identity no longer a covered product
        return RESOLUTION_IDENTITY_CHANGED

    @staticmethod
    def _cleanup():
        """Evaluations no identity needs, vulnerabilities nothing refers to."""
        context = Context()
        needed = set()
        for (
            status,
            scheme,
            product,
            version,
            platform_key,
            origin,
        ) in SoftwareIdentity.objects.filter(
            Q(scheme="purl") | Q(scheme="cpe")
        ).values_list(
            "status",
            "scheme",
            "product",
            "version",
            "entry__platform_key",
            "entry__package_origin",
        ):
            if is_covered(status, scheme):
                key = context.key(scheme, product, version, platform_key or "", origin)
                if key is not None:
                    needed.add(key)
        stale = [
            row[0]
            for row in Evaluation.objects.values_list(
                "id", "scheme", "product", "version", "platform_key", "extended"
            )
            if EvaluationKey(*row[1:]) not in needed
        ]
        for _, chunk in _chunks(stale):
            Evaluation.objects.filter(id__in=chunk).delete()
        Vulnerability.objects.filter(
            findings__isnull=True, exposures__isnull=True
        ).delete()


def _out_of_window(exposure, installations):
    year = nvd.cve_year(Vulnerability.objects.get(pk=exposure.vulnerability_id).vuln_id)
    return bool(year) and year not in installations.context.window
