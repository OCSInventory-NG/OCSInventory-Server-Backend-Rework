import logging
import re
from datetime import date, timedelta

import requests
from django.conf import settings
from django.utils import timezone

LOGGER = logging.getLogger(__name__)

_EOL_API_BASE = settings.EOL_API_BASE_URL
_CACHE_TTL = timedelta(hours=24)


def _get_win_build_channel():
    from .models import WindowsBuildMapping

    return {m.build: m.channel for m in WindowsBuildMapping.objects.all()}


def _fetch_eol(product, cycle):
    """
    Resolve the EOL data for a product/cycle pair.

    Reads EOLCache first: a cache entry younger than _CACHE_TTL is returned
    without hitting the network. Otherwise queries endoflife.date and refreshes
    the cache (update_or_create bumps fetched_at via auto_now).

    Returns a dict with keys product, cycle, eol, is_eol, support,
    support_date, latest — or None on HTTP/network failure.
    """
    from .models import EOLCache

    product = product.lower()
    cycle = str(cycle).lower()

    cached = EOLCache.objects.filter(
        product=product,
        cycle=cycle,
        fetched_at__gte=timezone.now() - _CACHE_TTL,
    ).first()
    if cached is not None:
        LOGGER.info("EOL cache hit for %s/%s", product, cycle)
        return {
            "product": product,
            "cycle": cycle,
            "eol": cached.eol,
            "is_eol": cached.is_eol,
            "support": cached.support,
            "support_date": cached.support_date,
            "latest": cached.latest,
        }

    try:
        url = f"{_EOL_API_BASE.rstrip('/')}/{product}/{cycle}.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None

        data = resp.json()
        eol_raw = data.get("eol")

        if isinstance(eol_raw, str):
            try:
                eol_date = date.fromisoformat(eol_raw)
                is_eol = date.today() >= eol_date
                eol_str = eol_raw
            except ValueError:
                is_eol = False
                eol_str = eol_raw
        elif isinstance(eol_raw, bool):
            is_eol = eol_raw
            eol_str = None
        else:
            is_eol = False
            eol_str = None

        # Extended support currently active (future date or explicit True)
        support_raw = data.get("extendedSupport")
        support_active = False
        support_date_str = support_raw if isinstance(support_raw, str) else None
        if isinstance(support_raw, str):
            try:
                support_active = date.today() < date.fromisoformat(support_raw)
            except ValueError:
                support_active = False
                support_date_str = None
        elif isinstance(support_raw, bool):
            support_active = support_raw

        # Extended support only matters once normal support has already ended.
        # If the cycle is still within its normal EOL window, extendedSupport
        # is irrelevant yet, even when the provider already lists a date for it.
        if is_eol and support_active:
            is_eol = False
        else:
            support_active = False
            support_date_str = None

        defaults = {
            "eol": eol_str,
            "is_eol": is_eol,
            "support": support_active,
            "support_date": support_date_str,
            "latest": data.get("latest"),
        }
        EOLCache.objects.update_or_create(
            product=product, cycle=cycle, defaults=defaults
        )

        return {"product": product, "cycle": cycle, **defaults}

    except Exception:
        LOGGER.exception("EOL fetch failed for %s/%s", product, cycle)
        return None


def _guess_eol(osname, osversion):
    """
    Best-effort attempt to query endoflife.date from raw OCS osname/osversion.

    Strategy (no mapping table):
      - product : first word of osname, lowercased
      - cycle   : osversion if it looks like a version, else first number in osname

    Returns the _fetch_eol result or None.
    """
    if not osname:
        return None

    if "windows" in osname.lower():
        if "server" in osname.lower():
            m = re.search(r"\b(\d{4,})\b", osname)
            if not m:
                return None
            return _fetch_eol("windows-server", m.group(1))
        else:
            parts = str(osversion or "").split(".")
            # Windows 11 still reports version 10.0.x, so the marketing major
            # (10 vs 11) must come from the OS name, not from osversion.
            m_major = re.search(r"windows\s+(\d+)", osname.lower())
            major = m_major.group(1) if m_major else (parts[0] if parts else None)
            build = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else None
            channel = _get_win_build_channel().get(build) if build else None
            if not channel or not major:
                return None
            osname_lower = osname.lower()
            if any(e in osname_lower for e in ("enterprise", "education")):
                suffix = "-e"
            else:
                suffix = "-w"
            cycle = f"{major}-{channel}"
            result = _fetch_eol("windows", f"{cycle}{suffix}")
            if result is None:
                result = _fetch_eol("windows", cycle)
            return result

    words = osname.lower().split()
    cycle = osversion
    if not cycle:
        m = re.search(r"\d[\d.]*", osname)
        cycle = m.group(0) if m else None
    if not cycle:
        return None
    parts = str(cycle).split(".")
    cycle_major_minor = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else parts[0]
    cycle_major = parts[0]

    for product in _product_candidates(words):
        result = _fetch_eol(product, cycle_major_minor)
        if result is None and cycle_major != cycle_major_minor:
            result = _fetch_eol(product, cycle_major)
        if result is not None:
            return result
    return None


def _product_candidates(words):
    """
    Yield product slug candidates from OS name words, most specific first.
    Stops building the slug when a word starts with a digit (version number).
    e.g. ["centos", "stream", "9"] → ["centos-stream", "centos"]
    e.g. ["rocky", "linux", "8.5"] → ["rocky-linux", "rocky"]
    e.g. ["ubuntu", "22.04", "lts"] → ["ubuntu"]
    """
    slug_words = []
    for w in words:
        if re.match(r"\d", w):
            break
        # sanitize: replace non-alphanumeric chars with hyphens, collapse repeats
        w = re.sub(r"[^a-z0-9]+", "-", w).strip("-")
        if w:
            slug_words.append(w)
    if not slug_words:
        return
    for i in range(len(slug_words), 0, -1):
        yield "-".join(slug_words[:i])
        if i == 2:
            yield "".join(slug_words[:2])


def _apply_custom_eol_override(result):
    """
    If an active CustomEOLExtendedSupport entry exists for this product/cycle,
    force is_eol to False and mark the asset as covered by extended support.
    """
    if not result or not result.get("is_eol"):
        return result

    from .models import CustomEOLExtendedSupport
    has_override = CustomEOLExtendedSupport.objects.filter(
        product=result["product"].lower(),
        cycle=result["cycle"].lower(),
        is_extended=True,
    ).exists()

    if has_override:
        return {**result, "is_eol": False, "support": True}
    return result


def resolve_asset_eol(asset):
    """
    Resolve the OS EOL status for an asset from its raw osname/osversion,
    applying any purchased extended-support override.

    Returns the EOL dict {product, cycle, eol, is_eol, support, latest}
    or None if the OS could not be resolved.
    """
    return _apply_custom_eol_override(_guess_eol(
        getattr(asset, "osname", None),
        getattr(asset, "osversion", None),
    ))


def update_asset_eol_status(asset):
    """
    Resolve and persist the OS EOL status for a single asset in AssetEOLStatus.

    Owned entirely by the EOL feature (EOLUpdate automation task). It is fully
    independent from the compliance rule engine, which never triggers or reads
    EOL resolution.
    """
    from .models import AssetEOLStatus

    eol = resolve_asset_eol(asset) or {}
    AssetEOLStatus.objects.update_or_create(
        asset=asset,
        defaults={
            "product":      eol.get("product"),
            "cycle":        eol.get("cycle"),
            "eol":          eol.get("eol"),
            "is_eol":       eol.get("is_eol", False),
            "support":      eol.get("support", False),
            "support_date": eol.get("support_date"),
            "latest":       eol.get("latest"),
        },
    )
