"""
Daily synchronization of the local vulnerability data. Each source is loaded
on its own: a source that fails keeps its previous data, and becomes stale
after STALE_AFTER without success.
"""

import logging
import os
import socket
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from security import config as security_config
from security.models import (
    OSV_SOURCES,
    SOURCE_EPSS,
    SOURCE_KEV,
    SOURCE_NVD,
    SOURCES,
    NvdCve,
    ScanLock,
    SourceSync,
)
from security.sources import epss, fetch, kev, nvd, osv

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(hours=48)
LOCK_TAKEOVER = timedelta(hours=12)
LOCK_NAME = "security"

# State of a source's data
NEVER_LOADED = "never_loaded"
STALE = "stale"
FRESH = "fresh"


def source_state(sync, now=None):
    """never_loaded, stale or fresh."""
    if sync is None or sync.last_success is None:
        return NEVER_LOADED
    if (now or timezone.now()) - sync.last_success > STALE_AFTER:
        return STALE
    return FRESH


def source_syncs():
    """{source: SourceSync}, every source present."""
    syncs = {sync.source: sync for sync in SourceSync.objects.all()}
    return {
        source: syncs.get(source) or SourceSync(source=source) for source in SOURCES
    }


# Lock shared by the synchronization and the scans


class LockBusy(Exception):
    """Another synchronization or scan holds the lock."""


def holder_name():
    return f"{socket.gethostname()}:{os.getpid()}"[:128]


def acquire_lock(now=None, name=LOCK_NAME):
    """Takes the lock, or the lock of a run that stopped more than 12 h ago."""
    now = now or timezone.now()
    holder = holder_name()
    try:
        with transaction.atomic():
            ScanLock.objects.create(name=name, holder=holder, acquired_at=now)
            return True
    except IntegrityError:
        pass
    taken = ScanLock.objects.filter(
        name=name, acquired_at__lt=now - LOCK_TAKEOVER
    ).update(holder=holder, acquired_at=now)
    if not taken:
        raise LockBusy(
            f"{name} lock held since {ScanLock.objects.get(name=name).acquired_at}"
        )
    logger.warning("Security lock taken over: its holder stopped more than 12 h ago")
    return True


def release_lock(name=LOCK_NAME):
    ScanLock.objects.filter(name=name).delete()


class locked:
    """with locked(): ... runs under the shared lock."""

    def __init__(self, now=None):
        self.now = now

    def __enter__(self):
        acquire_lock(self.now)
        return self

    def __exit__(self, *exc):
        release_lock()
        return False


# Loaders: each returns (record count, details, fingerprint)


def _load_osv(source, sync, get):
    url = osv.archive_url(settings.OSV_DATA_URL, source)
    path, fingerprint = fetch.download(url, sync.fingerprint, get=get)
    logger.debug("Loading %s into the database", url)
    try:
        count, details = osv.load(source, path)
    finally:
        os.unlink(path)
    return count, details, fingerprint


def _load_single(loader, url, sync, get):
    path, fingerprint = fetch.download(url, sync.fingerprint, get=get)
    logger.debug("Loading %s into the database", url)
    try:
        count, details = loader(path)
    finally:
        os.unlink(path)
    return count, details, fingerprint


def _load_nvd(sync, get, now):
    """
    Every year from 2002: the window's years with their CPE matches, the
    others with their scores only (checked again weekly). A year is
    downloaded when its .meta sha256 changed or it moves in or out of the
    window.
    """
    years_window = set(nvd.window(security_config.current().nvd_years, now))
    previous = (sync.fingerprint or {}).get("years", {})
    years = {}
    for year in range(nvd.FIRST_YEAR, now.year + 1):
        full = year in years_window
        known = previous.get(str(year)) or {}
        if not full and known.get("full") is False and known.get("checked"):
            checked = datetime.fromisoformat(known["checked"])
            if now - checked < nvd.SCORE_YEARS_RECHECK:
                years[str(year)] = known
                continue
        url = settings.NVD_CVE_FEED_URL.format(year=year)
        meta = nvd.parse_meta(fetch.read_text(url[: -len(".json.gz")] + ".meta", get))
        sha = meta.get("sha256", "")
        if sha and known.get("sha256") == sha and known.get("full") == full:
            years[str(year)] = {**known, "checked": now.isoformat()}
            continue
        path, _ = fetch.download(url, None, get=get)
        logger.debug("Loading NVD %s into the database", year)
        try:
            count = nvd.load_year(year, path, full)
        finally:
            os.unlink(path)
        years[str(year)] = {
            "sha256": sha,
            "full": full,
            "count": count,
            "checked": now.isoformat(),
        }
        logger.info(
            "NVD %s loaded: %s CVEs (%s)", year, count, "full" if full else "scores"
        )
    # Years before FIRST_YEAR or after a clock change: nothing to keep
    NvdCve.objects.exclude(year__in=[int(year) for year in years]).delete()
    count = NvdCve.objects.filter(full=True).count()
    return count, {"window": sorted(years_window)}, {"years": years}


class SyncService:
    """Loads the sources into the local data."""

    @classmethod
    def run(cls, sources=None, now=None, get=fetch.http_get, progress=None):
        """{source: "loaded" | "unchanged" | error message}."""
        now = now or timezone.now()
        progress = progress or logger.info
        results = {}
        for source in sources or SOURCES:
            sync, _ = SourceSync.objects.get_or_create(source=source)
            sync.last_attempt = now
            logger.debug("%s: checking for new data", source)
            try:
                if source in OSV_SOURCES:
                    count, details, fingerprint = _load_osv(source, sync, get)
                elif source == SOURCE_NVD:
                    count, details, fingerprint = _load_nvd(sync, get, now)
                elif source == SOURCE_KEV:
                    count, details, fingerprint = _load_single(
                        kev.load, settings.KEV_URL, sync, get
                    )
                elif source == SOURCE_EPSS:
                    count, details, fingerprint = _load_single(
                        epss.load, settings.EPSS_URL, sync, get
                    )
                else:
                    raise ValueError(f"Unknown source {source}")
            except fetch.Unchanged:
                sync.last_success = now
                sync.error = ""
                sync.save()
                results[source] = "unchanged"
                progress(f"{source}: unchanged")
                continue
            except Exception as error:
                logger.exception("Vulnerability source %s failed", source)
                sync.error = str(error)[:2000]
                sync.save()
                results[source] = sync.error
                progress(f"{source}: failed, previous data kept ({error})")
                continue
            sync.last_success = now
            sync.error = ""
            sync.record_count = count
            sync.details = details
            sync.fingerprint = fingerprint
            sync.save()
            results[source] = "loaded"
            progress(f"{source}: {count} records loaded")
        return results
