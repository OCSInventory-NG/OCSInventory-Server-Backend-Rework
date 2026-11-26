"""
The security criteria of the search.

- "vulnerabilities": the open vulnerabilities of a machine, exclusions
  applied; the conditions of one AND-group on it match the same
  vulnerability of the same product ("critical AND without fix").
- "security": the machine as a whole, as stored by security.asset_security;
  a machine without row is not scanned yet and has no vulnerability.
"""

import datetime
from collections import defaultdict

from django.db.models import F, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from security.asset_security import LEVELS, NOT_SCANNED, STATUSES
from security.exclusions import visible_exposures

VULNERABILITIES = "vulnerabilities"
SECURITY = "security"
OBJECTS = (VULNERABILITIES, SECURITY)
# What reading them requires, beyond seeing the assets
PERMISSION = "security.view_vulnerability"

TEXT = "text"
NUMBER = "number"
DATE = "date"
CHOICE = "choice"
YES_NO = "yes_no"
OPERATORS = {
    TEXT: {
        "exact",
        "iexact",
        "contains",
        "icontains",
        "startswith",
        "istartswith",
        "endswith",
        "iendswith",
    },
    NUMBER: {"exact", "gt", "gte", "lt", "lte"},
    DATE: {"gt", "gte", "lt", "lte"},
    CHOICE: {"exact", "iexact"},
    YES_NO: {"exact", "iexact"},
}
YES = {True, 1, "1", "true", "yes", "True"}
NO = {False, 0, "0", "false", "no", "False"}

# field: (lookup on the exposure, kind, choices)
VULNERABILITY_FIELDS = {
    "vuln_id": ("vulnerability__vuln_id", TEXT, None),
    "level": ("vulnerability__level", CHOICE, LEVELS),
    "cvss_score": ("vulnerability__cvss_score", NUMBER, None),
    "epss": ("vulnerability__epss", NUMBER, None),
    "kev": ("vulnerability__kev", YES_NO, None),
    "fix_available": (None, YES_NO, None),
    "software_name": ("software_name", TEXT, None),
    "version": ("version", TEXT, None),
    "first_seen": ("first_seen", DATE, None),
}
# field: (column of security.AssetSecurity, kind, choices, value without row)
SECURITY_FIELDS = {
    "status": ("status", CHOICE, STATUSES, NOT_SCANNED),
    "cves": ("cves", NUMBER, None, 0),
    "cves_fixable": ("cves_fixable", NUMBER, None, 0),
}
# What a matched vulnerability shows, the most serious first
MATCHED = {
    "id": "id",
    "vuln_id": "vulnerability__vuln_id",
    "level": "vulnerability__level",
    "cvss_score": "vulnerability__cvss_score",
    "kev": "vulnerability__kev",
    "epss": "vulnerability__epss",
    "software_name": "software_name",
    "version": "version",
    "fixed_version": "fixed_version",
    "first_seen": "first_seen",
}


def fields(obj):
    return VULNERABILITY_FIELDS if obj == VULNERABILITIES else SECURITY_FIELDS


def _value(kind, choices, value):
    """The value compared, checked against its kind; ValueError otherwise."""
    if kind == YES_NO:
        if value in YES:
            return True
        if value in NO:
            return False
        raise ValueError("yes or no")
    if kind == NUMBER:
        if isinstance(value, bool):
            raise ValueError("a number")
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError("a number") from None
    if kind == DATE:
        parsed = None
        if isinstance(value, str):
            try:
                parsed = parse_date(value) or parse_datetime(value)
            except ValueError:
                parsed = None
        if parsed is None:
            raise ValueError("a date, YYYY-MM-DD")
        if isinstance(parsed, datetime.datetime) and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
    if not isinstance(value, str) or not value:
        raise ValueError("a text")
    if choices is not None:
        value = value.lower()
        if value not in choices:
            raise ValueError("among " + ", ".join(choices))
    return value


def validate(condition):
    """ValueError with the reason when the condition is not accepted."""
    obj, field = condition["object"], condition.get("field")
    spec = fields(obj).get(field)
    if spec is None:
        raise ValueError(f"{obj}: unknown field {field}")
    kind, choices = spec[1], spec[2]
    if condition.get("operator") not in OPERATORS[kind]:
        raise ValueError(
            f"{obj}.{field}: operator among " + ", ".join(sorted(OPERATORS[kind]))
        )
    try:
        _value(kind, choices, condition.get("value"))
    except ValueError as error:
        raise ValueError(f"{obj}.{field}: {error}") from None


def exposure_q(condition):
    """The condition on an open exposure."""
    lookup, kind, choices = VULNERABILITY_FIELDS[condition["field"]]
    operator = condition["operator"]
    value = _value(kind, choices, condition["value"])
    if condition["field"] == "fix_available":
        return ~Q(fixed_version="") if value else Q(fixed_version="")
    if (
        kind == DATE
        and isinstance(value, datetime.date)
        and not isinstance(value, datetime.datetime)
    ):
        lookup = f"{lookup}__date"
    return Q(**{f"{lookup}__{operator}": value})


def _matches(default, operator, value):
    if operator in ("exact", "iexact"):
        return default == value
    return {
        "gt": default > value,
        "gte": default >= value,
        "lt": default < value,
        "lte": default <= value,
    }[operator]


def security_q(condition):
    """The condition on the machine, a machine without row as not scanned."""
    column, kind, choices, default = SECURITY_FIELDS[condition["field"]]
    operator = condition["operator"]
    value = _value(kind, choices, condition["value"])
    if operator == "iexact":
        operator = "exact"
    q = Q(**{f"security__{column}__{operator}": value})
    if _matches(default, operator, value):
        q |= Q(security__isnull=True)
    return q


def asset_ids(q, now=None):
    """The machines with an open vulnerability matching q, as a subquery."""
    return visible_exposures(now).filter(q).values("asset_id")


def rows_queryset(inventory_ids, q, now=None):
    """The matching open vulnerabilities of the given machines."""
    return visible_exposures(now).filter(asset_id__in=inventory_ids).filter(q)


def matched(inventory_ids, q, now=None):
    """{asset_id: [vulnerability]}: what matched, the most serious first."""
    result = defaultdict(list)
    rows = (
        rows_queryset(inventory_ids, q, now)
        .order_by(
            F("vulnerability__cvss_score").desc(nulls_last=True),
            "vulnerability__vuln_id",
            "id",
        )
        .values("asset_id", *MATCHED.values())
    )
    for row in rows:
        result[row["asset_id"]].append(
            {name: row[lookup] for name, lookup in MATCHED.items()}
        )
    return result


def uses_security(search):
    """Whether a stored search (a dynamic group's) has a security criterion."""
    if isinstance(search, dict):
        search = search.get("search_data")
    return any(
        isinstance(condition, dict) and condition.get("object") in OBJECTS
        for group in (search if isinstance(search, list) else [])
        if isinstance(group, list)
        for condition in group
    )
