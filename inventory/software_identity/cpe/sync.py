import json
import logging
import math
import re
import tarfile
from collections import Counter

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from inventory.software_identity.cpe.tokens import base_title, title_entries
from inventory.software_identity.models import CpeIndexState, CpeProduct, CpeToken

logger = logging.getLogger(__name__)

TIMEOUT = 900
BATCH_SIZE = 5000
MAX_LENGTH = 255
_UNESCAPED_COLON = re.compile(r"(?<!\\):")
_ESCAPED = re.compile(r"\\(.)")


def http_open(url):
    """Stream a URL: the 84 MB feed is read as it arrives, never written to disk."""
    response = requests.get(url, stream=True, timeout=TIMEOUT)
    response.raise_for_status()
    response.raw.decode_content = True
    return response.raw


def sync_cpe_index(open_url=http_open):
    """
    Rebuild the CPE index when the NVD CPE dictionary changed.
    Returns True when the index was rebuilt, False when the feed is unchanged.
    """
    meta = _parse_meta(open_url(settings.NVD_CPE_META_URL).read().decode())
    state = CpeIndexState.current()
    if meta.get("sha256") and meta["sha256"] == state.source_sha256:
        logger.info("NVD CPE dictionary unchanged since %s", state.source_date)
        return False

    products = _read_feed(open_url(settings.NVD_CPE_FEED_URL))
    if not products or len(products) * 2 < state.product_count:
        raise ValueError(
            f"NVD CPE feed refused: {len(products)} applications against "
            f"{state.product_count} in the current index, the index is kept"
        )
    with transaction.atomic():
        _replace_index(products)
        state.version += 1
        state.source_sha256 = meta.get("sha256", "")
        state.source_date = meta.get("lastModifiedDate", "")
        state.synced_at = timezone.now()
        state.product_count = len(products)
        state.save()
    logger.info(
        "CPE index version %s built with %s products", state.version, len(products)
    )
    return True


def _parse_meta(text):
    meta = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta


def _read_feed(stream):
    """Feed applications: {(vendor, product): {titles, versions, popularity}}."""
    products = {}
    with tarfile.open(fileobj=stream, mode="r|gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            for item in json.load(archive.extractfile(member)).get("products", []):
                _add_cpe(products, item.get("cpe", {}))
    return {key: data for key, data in products.items() if data["titles"]}


def _add_cpe(products, cpe):
    parts = [
        _ESCAPED.sub(r"\1", part)
        for part in _UNESCAPED_COLON.split(cpe.get("cpeName", ""))
    ]
    if cpe.get("deprecated") or len(parts) < 6 or parts[2] != "a":
        return
    vendor, product, version = parts[3], parts[4], parts[5]
    if len(vendor) > MAX_LENGTH or len(product) > MAX_LENGTH:
        return
    data = products.setdefault(
        (vendor, product), {"titles": Counter(), "versions": set(), "popularity": 0}
    )
    data["popularity"] += 1
    titles = cpe.get("titles", [])
    title = next((entry["title"] for entry in titles if entry.get("lang") == "en"), "")
    base = base_title(title, version)
    if base:
        data["titles"][base] += 1
    if version not in ("*", "-"):
        data["versions"].add(version)


def _replace_index(products):
    CpeToken.objects.all().delete()
    # The tokens are gone: skip the collector, which would load every product
    # and its JSON just to find nothing left to cascade
    CpeProduct.objects.all()._raw_delete(CpeProduct.objects.db)
    CpeProduct.objects.bulk_create(
        (
            CpeProduct(
                vendor=vendor,
                product=product,
                titles=dict(data["titles"]),
                versions=sorted(data["versions"]),
                popularity=data["popularity"],
            )
            for (vendor, product), data in products.items()
        ),
        batch_size=BATCH_SIZE,
    )
    # Read the ids back: bulk_create does not return them on every database
    ids = {
        (vendor, product): pk
        for pk, vendor, product in CpeProduct.objects.values_list(
            "id", "vendor", "product"
        )
    }

    words_by_product = {}
    frequency = Counter()
    for (vendor, product), data in products.items():
        _, entries = title_entries(vendor, product, data["titles"])
        words = {word for entry in entries for word in entry if len(word) <= MAX_LENGTH}
        words_by_product[ids[(vendor, product)]] = words
        frequency.update(words)

    total = len(products)
    CpeToken.objects.bulk_create(
        (
            CpeToken(
                token=word,
                product_id=product_id,
                weight=math.log(total / frequency[word]),
            )
            for product_id, words in words_by_product.items()
            for word in words
        ),
        batch_size=BATCH_SIZE,
    )
