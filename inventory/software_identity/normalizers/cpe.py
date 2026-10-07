import re

from inventory.software_identity.match_key import match_key

from .base import MATCHED, NONE, REVIEW, UNSUPPORTED, VALIDATED, IdentityResult

# Measured on the dev fleet (cve-poc/cpe_title_match.py): 12 automatic
# decisions out of 14 correct on Windows, 11 out of 11 on macOS
MATCH_SCORE = 0.9
MATCH_LEAD = 0.1
REVIEW_SCORE = 0.5
_CPE_SPECIAL = re.compile(r"([^A-Za-z0-9_.\-])")
_LEADING_VERSION = re.compile(r"\d+(\.\d+)*")


def cpe_version(version):
    match = _LEADING_VERSION.match((version or "").strip())
    return match.group(0) if match else ""


def _escape(value):
    return _CPE_SPECIAL.sub(r"\\\1", value)


def cpe_identifier(product, version):
    vendor, name = product.split(":", 1)
    escaped_version = _escape(version) if version else "*"
    return (
        f"cpe:2.3:a:{_escape(vendor)}:{_escape(name)}:{escaped_version}"
        ":*:*:*:*:*:*:*"
    )


class CpeNormalizer:
    """Windows and macOS applications: catalog decision first, then the CPE index."""

    family = ""

    def __init__(self, matcher, decisions):
        self.matcher = matcher
        self.decisions = decisions

    def is_os_component(self, record):
        return False

    def normalize(self, record):
        key = match_key(record.name)
        version = cpe_version(record.version)
        decision = self.decisions.get((self.family, key))
        if decision is not None:
            if decision.product is None:
                return IdentityResult(
                    NONE,
                    key,
                    reason="decided_none",
                    version=version,
                    decision_id=decision.id,
                )
            return self._identity(
                VALIDATED, key, decision.product, version, decision_id=decision.id
            )
        if self.is_os_component(record):
            return IdentityResult(
                UNSUPPORTED, key, reason="os_component", version=version
            )

        ranked = self.matcher.rank(record.name, record.publisher, record.version)
        candidates = [
            {"product": product, "score": score} for score, product in ranked[:3]
        ]
        best = ranked[0][0] if ranked else None
        if best is None or best < REVIEW_SCORE:
            return IdentityResult(
                NONE,
                key,
                reason="no_candidate",
                version=version,
                score=best,
                candidates=candidates,
            )
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        if best >= MATCH_SCORE and best - second >= MATCH_LEAD:
            return self._identity(
                MATCHED, key, ranked[0][1], version, score=best, candidates=candidates
            )
        return IdentityResult(
            REVIEW, key, version=version, score=best, candidates=candidates
        )

    @staticmethod
    def _identity(status, key, product, version, **extra):
        return IdentityResult(
            status,
            key,
            scheme="cpe",
            identifier=cpe_identifier(product, version),
            product=product,
            version=version,
            **extra,
        )
