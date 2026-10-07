"""
Ranks NVD CPE products for a software name. The scoring is the one measured
on the dev fleet (cve-poc/cpe_title_match.py), ported as is: title words
weighted by rarity, then the installed version and the year break ties.
"""

import math
import re

from inventory.software_identity.cpe.tokens import title_entries, tokens
from inventory.software_identity.models import CpeIndexState, CpeProduct, CpeToken

CANDIDATE_LIMIT = 2000
CACHE_SIZE = 1024
PUBLISHER_NOISE = {"inc", "llc", "ltd", "corporation", "corp", "sas"}
# A candidate unaware of the installed major only loses points when another
# candidate this close knows the installed version (Edge legacy vs Chromium)
COMPETITOR_RANGE = 0.5
YEAR = re.compile(r"(?<!\d)(19|20)\d\d(?!\d)")
_LEADING_VERSION = re.compile(r"\d+(\.\d+)*")


def clean_version(version):
    match = _LEADING_VERSION.match((version or "").strip())
    return match.group(0) if match else ""


def version_signal(installed, known):
    """Bonus when the installed version is known to the product,
    None when its major is not."""
    if not installed or not known:
        return 0.0
    for candidate in known:
        if (
            candidate == installed
            or installed.startswith(candidate + ".")
            or candidate.startswith(installed + ".")
        ):
            return 0.15
    parts = installed.split(".")
    if len(parts) >= 3 and any(
        candidate.split(".")[:3] == parts[:3] for candidate in known
    ):
        return 0.12
    if any(candidate.split(".")[0] == parts[0] for candidate in known):
        return 0.05
    return None


def year_signal(product, name):
    """A year in the product key (visual_studio_2026) must match the name's year."""
    product_years = {match.group(0) for match in YEAR.finditer(product)}
    if not product_years:
        return 0.0
    name_years = {match.group(0) for match in YEAR.finditer(name)}
    if product_years & name_years:
        return 0.1
    return -0.3 if name_years else -0.1


def title_score(name_words, publisher_words, candidate, weight):
    best = 0.0
    for words in candidate["entries"]:
        product_words = words - candidate["vendor_words"]
        name_weight, product_weight = weight(name_words), weight(product_words)
        if not product_words or not name_weight or not product_weight:
            continue
        name_cov = weight(name_words & words) / name_weight
        product_cov = weight(product_words & name_words) / product_weight
        if name_cov + product_cov:
            best = max(best, 2 * name_cov * product_cov / (name_cov + product_cov))
    if best and publisher_words & candidate["vendor_words"]:
        best += 0.05
    return best + 0.002 * math.log10(1 + candidate["popularity"])


def rank_candidates(
    name, publisher, version, name_words, candidates, weights, unknown_weight, limit
):
    publisher_words = set(tokens(publisher)) - PUBLISHER_NOISE

    def weight(words):
        return sum(weights.get(word, unknown_weight) for word in words)

    installed = clean_version(version)
    scored = []
    for candidate in candidates:
        score = title_score(name_words, publisher_words, candidate, weight)
        if score > 0:
            scored.append(
                [
                    score + year_signal(candidate["product"], name),
                    candidate["key"],
                    version_signal(installed, candidate["versions"]),
                ]
            )
    if not scored:
        return []

    best = max(item[0] for item in scored)
    competitor_knows = any(
        item[2] is not None and item[2] >= 0.12 and item[0] >= best - COMPETITOR_RANGE
        for item in scored
    )
    for item in scored:
        if item[2] is None:
            if competitor_knows:
                item[0] -= 0.3
        else:
            item[0] += item[2]
    ranked = sorted(
        ((round(score, 4), key) for score, key, _ in scored),
        key=lambda x: (-x[0], x[1]),
    )
    return ranked[:limit]


class CpeMatcher:
    """Ranks CPE products for software names, using the index stored in the database."""

    def __init__(self, candidate_limit=CANDIDATE_LIMIT):
        state = CpeIndexState.current()
        self.version = state.version
        if state.product_count > 1:
            self.unknown_weight = math.log(state.product_count)
        else:
            self.unknown_weight = 1.0
        self.candidate_limit = candidate_limit
        self._cache = {}

    @property
    def available(self):
        return self.version > 0

    def rank(self, name, publisher, version, limit=5):
        name_words = frozenset(tokens(re.sub(r":\w+$", "", name or "")))
        if not name_words:
            return []
        candidates, weights = self._candidates(name_words)
        return rank_candidates(
            name or "",
            publisher or "",
            version,
            name_words,
            candidates,
            weights,
            self.unknown_weight,
            limit,
        )

    def _candidates(self, name_words):
        if name_words not in self._cache:
            if len(self._cache) >= CACHE_SIZE:
                self._cache.clear()
            self._cache[name_words] = self._load_candidates(name_words)
        return self._cache[name_words]

    def _load_candidates(self, name_words):
        name_weights = self._weights(name_words)
        product_ids = []
        seen = set()
        # Rarest words first: they point to few, relevant products
        for word in sorted(name_weights, key=name_weights.get, reverse=True):
            ids = (
                CpeToken.objects.filter(token=word)
                .order_by("product_id")
                .values_list("product_id", flat=True)
            )
            for product_id in ids[: self.candidate_limit]:
                if product_id not in seen and len(product_ids) < self.candidate_limit:
                    seen.add(product_id)
                    product_ids.append(product_id)
            if len(product_ids) >= self.candidate_limit:
                break

        candidates = []
        title_words = set()
        rows = CpeProduct.objects.filter(id__in=product_ids).values(
            "vendor", "product", "titles", "versions", "popularity"
        )
        for row in rows:
            vendor_words, entries = title_entries(
                row["vendor"], row["product"], row["titles"]
            )
            title_words.update(*entries)
            candidates.append(
                {
                    "key": f"{row['vendor']}:{row['product']}",
                    "product": row["product"],
                    "vendor_words": vendor_words,
                    "entries": entries,
                    "popularity": row["popularity"],
                    "versions": row["versions"],
                }
            )
        return candidates, {**self._weights(title_words), **name_weights}

    @staticmethod
    def _weights(words):
        return dict(
            CpeToken.objects.filter(token__in=list(words))
            .values_list("token", "weight")
            .distinct()
        )
