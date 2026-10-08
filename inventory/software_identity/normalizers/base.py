from collections import namedtuple
from dataclasses import dataclass, field
from typing import Protocol

MATCHED = "matched"
VALIDATED = "validated"
REVIEW = "review"
NONE = "none"
UNSUPPORTED = "unsupported"
STATUSES = (MATCHED, VALIDATED, REVIEW, NONE, UNSUPPORTED)

# A catalog decision as the normalizers see it: product None means "no CPE"
EffectiveDecision = namedtuple("EffectiveDecision", "id product")


@dataclass(frozen=True)
class SoftwareRecord:
    name: str = ""
    publisher: str = ""
    version: str = ""
    architecture: str = ""
    package_format: str = ""
    source_package: str = ""
    platform_family: str = ""
    platform_key: str = ""
    # None: the mapping does not collect it; "": the package has no origin
    package_origin: str | None = None


@dataclass(frozen=True)
class IdentityResult:
    status: str
    match_key: str
    reason: str = ""
    scheme: str = ""
    identifier: str = ""
    product: str = ""
    version: str = ""
    score: float | None = None
    candidates: list = field(default_factory=list)
    decision_id: int | None = None


class Normalizer(Protocol):
    family: str

    def normalize(self, record: SoftwareRecord) -> IdentityResult: ...
