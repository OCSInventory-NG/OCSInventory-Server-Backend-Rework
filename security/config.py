"""
The security settings, a section of the general configuration (Config named
"security"): what the scan loads and how vulnerabilities are ordered. Each
item is rendered by the general configuration form from its "type".
"""

from dataclasses import dataclass, field

SECTION = "security"
PRIORITY_CRITERIA = ("kev", "score", "epss", "machines")
# A list whose order matters, its values taken among "options"
ORDERED_LIST = "ordered list"

ITEMS = [
    {
        "name": "nvd_years",
        "description": (
            "Years of NVD vulnerabilities loaded for Windows and macOS software,"
            " the current one included"
        ),
        "value": 3,
        "type": "number input",
        "unit": "years",
        "min": 1,
        "max": 25,
    },
    {
        "name": "priority",
        "description": "Order of the vulnerability list, first criterion first",
        "value": list(PRIORITY_CRITERIA),
        "type": ORDERED_LIST,
        "unit": "",
        "options": list(PRIORITY_CRITERIA),
    },
    {
        "name": "cpe_match_score",
        "description": (
            "Windows and macOS software: name match score from which the product"
            " is identified automatically"
        ),
        "value": 0.9,
        "type": "number input",
        "unit": "",
        "min": 0,
        "max": 1,
    },
    {
        "name": "cpe_review_score",
        "description": (
            "Windows and macOS software: name match score from which the product"
            " is proposed for review"
        ),
        "value": 0.5,
        "type": "number input",
        "unit": "",
        "min": 0,
        "max": 1,
    },
]
DEFAULTS = {item["name"]: item["value"] for item in ITEMS}


@dataclass(frozen=True)
class SecurityConfig:
    nvd_years: int = DEFAULTS["nvd_years"]
    priority: list = field(default_factory=lambda: list(PRIORITY_CRITERIA))
    cpe_match_score: float = DEFAULTS["cpe_match_score"]
    cpe_review_score: float = DEFAULTS["cpe_review_score"]

    @property
    def thresholds(self):
        return self.cpe_match_score, self.cpe_review_score


class InvalidSecurityConfig(ValueError):
    """{item name: message}"""

    def __init__(self, errors):
        super().__init__(errors)
        self.errors = errors


def _number(value):
    if isinstance(value, bool):
        raise ValueError
    return float(value)


def check(values):
    """
    The settings of {name: value}, missing names at their default. Raises
    InvalidSecurityConfig with a message per wrong item.
    """
    values = {**DEFAULTS, **values}
    errors = {}
    try:
        years = _number(values["nvd_years"])
        if years != int(years) or not 1 <= years <= 25:
            raise ValueError
    except (TypeError, ValueError):
        errors["nvd_years"] = "A whole number of years between 1 and 25"
    priority = values["priority"]
    if not isinstance(priority, list) or sorted(map(str, priority)) != sorted(
        PRIORITY_CRITERIA
    ):
        errors["priority"] = "Every criterion once: " + ", ".join(PRIORITY_CRITERIA)
    try:
        match = _number(values["cpe_match_score"])
        review = _number(values["cpe_review_score"])
        if not 0 < review < match <= 1:
            errors["cpe_review_score"] = "0 < review score < match score <= 1"
    except (TypeError, ValueError):
        errors["cpe_match_score"] = "Numbers between 0 and 1"
    if errors:
        raise InvalidSecurityConfig(errors)
    return SecurityConfig(
        nvd_years=int(_number(values["nvd_years"])),
        priority=[str(criterion) for criterion in priority],
        cpe_match_score=_number(values["cpe_match_score"]),
        cpe_review_score=_number(values["cpe_review_score"]),
    )


def values_of(items):
    """{name: value} of a configuration section's items."""
    return {
        item.get("name"): item.get("value")
        for item in items or []
        if isinstance(item, dict)
    }


def current():
    """The settings in force; the defaults while the section is missing or wrong."""
    from config.models import Config

    section = Config.objects.filter(name=SECTION).first()
    if section is None:
        return SecurityConfig()
    try:
        return check(values_of(section.value))
    except InvalidSecurityConfig:
        return SecurityConfig()
