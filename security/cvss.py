"""
CVSS base score of a 3.0 or 3.1 vector (formula of the FIRST specification,
https://www.first.org/cvss/v3.1/specification-document), and the level shown in
filters and badges.
"""

import math

_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}
_METRICS = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")

# Distribution ratings: Ubuntu priority, Debian urgency, Rocky and Alma severity
_RATINGS = {
    "critical": "critical",
    "high": "high",
    "important": "high",
    "medium": "medium",
    "moderate": "medium",
    "low": "low",
    "negligible": "low",
    "unimportant": "low",
}


def _roundup(value):
    """Smallest one decimal number not below value, without float artifacts."""
    integer = round(value * 100000)
    if integer % 10000 == 0:
        return integer / 100000.0
    return (math.floor(integer / 10000) + 1) / 10.0


def base_score(vector):
    """Base score of a CVSS 3.0 or 3.1 vector, None for any other vector."""
    parts = (vector or "").split("/")
    if not parts[0].startswith("CVSS:3."):
        return None
    metrics = dict(part.split(":", 1) for part in parts[1:] if ":" in part)
    try:
        values = {name: metrics[name] for name in _METRICS}
        changed = values["S"] == "C"
        if values["S"] not in ("U", "C"):
            return None
        iss = 1 - (
            (1 - _CIA[values["C"]])
            * (1 - _CIA[values["I"]])
            * (1 - _CIA[values["A"]])
        )
        privileges = (_PR_CHANGED if changed else _PR_UNCHANGED)[values["PR"]]
        exploitability = (
            8.22
            * _AV[values["AV"]]
            * _AC[values["AC"]]
            * privileges
            * _UI[values["UI"]]
        )
    except KeyError:
        return None

    if changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    else:
        impact = 6.42 * iss
    if impact <= 0:
        return 0.0
    if changed:
        return _roundup(min(1.08 * (impact + exploitability), 10))
    return _roundup(min(impact + exploitability, 10))


def level(score, rating=""):
    """critical, high, medium, low or unknown: from the score, else the rating."""
    if score:
        if score >= 9.0:
            return "critical"
        if score >= 7.0:
            return "high"
        if score >= 4.0:
            return "medium"
        return "low"
    return _RATINGS.get((rating or "").strip().lower(), "unknown")
