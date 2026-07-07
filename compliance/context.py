import logging
import re
from datetime import date

import requests
from django.conf import settings

LOGGER = logging.getLogger(__name__)

_ASSET_FIELDS = [
    "id",
    "name",
    "description",
    "serial",
    "osname",
    "osversion",
    "uuid",
    "srcip",
    "srcmac",
    "domain",
    "agent",
]

_EOL_API = settings.EOL_API_URL


def _get_win_build_channel():
    from .models import WindowsBuildMapping

    return {m.build: m.channel for m in WindowsBuildMapping.objects.all()}


def _fetch_eol(product, cycle):
    """
    Query endoflife.date for a product/cycle pair, then persist the result
    in EOLCache (update_or_create).

    Returns a dict with keys product, cycle, eol, is_eol, support, latest
    — or None on HTTP/network failure.
    """
    from .models import EOLCache

    product = product.lower()
    cycle = str(cycle).lower()

    try:
        url = _EOL_API.format(product=product, cycle=cycle)
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

        if is_eol:
            support_raw = data.get("extendedSupport")
            if isinstance(support_raw, str):
                try:
                    if date.today() < date.fromisoformat(support_raw):
                        is_eol = False
                except ValueError:
                    pass

        defaults = {
            "eol": eol_str,
            "is_eol": is_eol,
            "support": data.get("extendedSupport") or None,
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
            major = parts[0] if parts else None
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
    If a CustomEOLExtendedSupport entry exists for this product/cycle
    and its end date has not yet passed, force is_eol to False.
    """
    if not result or not result.get("is_eol"):
        return result

    from .models import CustomEOLExtendedSupport
    has_override = CustomEOLExtendedSupport.objects.filter(
        product=result["product"].lower(),
        cycle=result["cycle"].lower(),
        extended_support_until__gte=date.today(),
    ).exists()

    if has_override:
        return {**result, "is_eol": False}
    return result


def build_context(asset):
    """
    Build the JSON Logic evaluation context for a given InventoryBase instance.

    Context keys:
        - scalar InventoryBase fields (name, osname, osversion, …)
        - softwares       : list of {name, publisher, version, …}
        - softwares_names : flat lowercase list for fast blacklist checks
        - os_eol          : {product, cycle, eol, is_eol, support, latest}
                            or None if the OS could not be resolved
    """
    context = {field: getattr(asset, field, None) for field in _ASSET_FIELDS}

    try:
        softwares = list(
            asset.software_dictionary_entries.values(
                "name",
                "publisher",
                "version",
                "major_version",
                "minor_version",
                "patch_version",
            )
        )
    except Exception:
        LOGGER.exception("Failed to fetch softwares for asset %s", asset.id)
        softwares = []

    context["softwares"] = softwares
    context["softwares_names"] = [s["name"].lower() for s in softwares if s["name"]]
    context["softwares_versions"] = {
        s["name"].lower(): s["major_version"]
        for s in softwares
        if s["name"] and s["major_version"] is not None
    }

    context["os_eol"] = _apply_custom_eol_override(_guess_eol(
        getattr(asset, "osname", None),
        getattr(asset, "osversion", None),
    ))

    try:
        inventory = {}
        for inv_section in asset.inventory_sections.prefetch_related(
            "fields__template_field"
        ):
            for inv_field in inv_section.fields.all():
                if inv_field.template_field_id is not None:
                    inventory[str(inv_field.template_field_id)] = inv_field.value
        context["inventory"] = inventory
    except Exception:
        LOGGER.exception("Failed to fetch inventory fields for asset %s", asset.id)
        context["inventory"] = {}

    try:
        context["group_ids"] = list(asset.assetgroup_set.values_list("id", flat=True))
    except Exception:
        LOGGER.exception("Failed to fetch group_ids for asset %s", asset.id)
        context["group_ids"] = []

    try:
        accountinfo_obj = asset.accountinfo.first()
        context["accountinfo"] = accountinfo_obj.accountdata if accountinfo_obj and accountinfo_obj.accountdata else {}
    except Exception:
        LOGGER.exception("Failed to fetch accountinfo for asset %s", asset.id)
        context["accountinfo"] = {}

    return context
