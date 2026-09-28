import logging

LOGGER = logging.getLogger(__name__)

CONFIG_NAME = "cve_integration"

# Single source of truth for the "cve_integration" Config entry, in the
# generic settings-item format used across the app (server, agent, ...):
# {name, description, value, type, unit, options?}. Reused by the initial
# migration to seed the entry and by get_cve_config() to read it back.
CVE_CONFIG_ITEMS = [
    {
        "name": "vulnerability_lookup_url",
        "description": "Base URL of the self-hosted Vulnerability-Lookup instance",
        "value": "",
        "type": "text input",
        "unit": "",
    },
    {
        "name": "cpe_guesser_url",
        "description": "Base URL of the self-hosted cpe-guesser instance",
        "value": "",
        "type": "text input",
        "unit": "",
    },
    {
        "name": "min_confidence_rank",
        "description": "Minimum cpe-guesser rank required to auto-confirm a CPE match",
        "value": 100,
        "type": "number input",
        "unit": "",
    },
    {
        "name": "cache_validity_hours",
        "description": "Hours before a CPE match / CVE report is re-queried",
        "value": 24,
        "type": "number input",
        "unit": "hours",
    },
    {
        "name": "show_cve_url",
        "description": "Show a link to the CVE record (NVD) in CVE reports",
        "value": True,
        "type": "switch",
        "unit": "",
    },
]

_DEFAULTS = {item["name"]: item["value"] for item in CVE_CONFIG_ITEMS}


def get_cve_config():
    """
    Read the "cve_integration" Config entry, falling back to safe defaults
    for any missing key (or if the entry does not exist at all).

    Never raises: a missing/malformed config must not break the scheduled
    enrichment task, it should just run with defaults and log a warning.
    """
    from config.models import Config

    config = _DEFAULTS.copy()

    entry = Config.objects.filter(name=CONFIG_NAME).first()
    if not entry:
        LOGGER.warning(
            "No '%s' config entry found, using default CVE integration settings",
            CONFIG_NAME,
        )
        return config

    if not isinstance(entry.value, list):
        LOGGER.warning(
            "'%s' config value is not a list of settings items, using default CVE integration settings",
            CONFIG_NAME,
        )
        return config

    for item in entry.value:
        if isinstance(item, dict) and item.get("name") in config:
            config[item["name"]] = item.get("value")

    return config
