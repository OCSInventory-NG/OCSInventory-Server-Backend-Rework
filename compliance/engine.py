import logging

from asset.inventory_base.models import InventoryBase
from automation.rule.jsonlogic import jsonLogic

from .context import build_context
from .models import AssetEOLStatus, ComplianceResult, ComplianceRule

LOGGER = logging.getLogger(__name__)


def evaluate_rule(rule, context):
    """
    Evaluate a single rule against a pre-built context dict.

    Convention: jsonLogic returning True means the asset is COMPLIANT
    (same as automation rules: True = condition is met).

    Returns:
        (status, detail) where status is a ComplianceResult.STATUS_* constant
        and detail is a dict stored for display purposes.
    """
    try:
        triggered = bool(jsonLogic(rule.logic, context))
        status = (
            ComplianceResult.STATUS_COMPLIANT
            if triggered
            else ComplianceResult.STATUS_NON_COMPLIANT
        )
        return status, {"triggered": triggered}
    except Exception as exc:
        LOGGER.error(
            "Error evaluating rule %s (%s): %s",
            rule.id, rule.name, exc,
        )
        return ComplianceResult.STATUS_UNKNOWN, {"error": str(exc)}


def evaluate_asset(asset):
    """
    Evaluate all enabled rules against a single asset and persist results.

    Called by the compliance automation task or the manual evaluate endpoint.
    Also persists AssetEOLStatus from the OS EOL data.

    Returns a list of dicts {asset_id, rule_id, status} for reporting.
    """
    context = build_context(asset)

    eol = context.get("os_eol") or {}
    AssetEOLStatus.objects.update_or_create(
        asset=asset,
        defaults={
            "product": eol.get("product"),
            "cycle":   eol.get("cycle"),
            "eol":     eol.get("eol"),
            "is_eol":  eol.get("is_eol", False),
            "support": eol.get("support"),
            "latest":  eol.get("latest"),
        },
    )

    all_rules = list(ComplianceRule.objects.filter(enabled=True))

    ComplianceResult.objects.filter(asset=asset).exclude(
        rule_id__in=[r.id for r in all_rules]
    ).delete()

    report = []

    for rule in all_rules:
        status, detail = evaluate_rule(rule, context)
        ComplianceResult.objects.update_or_create(
            asset=asset,
            rule=rule,
            defaults={"status": status, "detail": detail},
        )
        report.append({
            "asset_id": asset.id,
            "rule_id": rule.id,
            "status": status,
        })
        LOGGER.debug("Asset %s / Rule %s → %s", asset.id, rule.id, status)

    LOGGER.info(
        "Compliance evaluated for asset %s: %d rule(s)", asset.id, len(report)
    )
    return report


def run_evaluation():
    """
    Evaluate all enabled rules against all assets and persist results.

    Intended for bulk re-evaluation triggered manually via the API.
    For per-asset evaluation at inventory time, use evaluate_asset() instead.

    Returns a list of dicts {asset_id, rule_id, status} for reporting.
    """
    assets = list(InventoryBase.objects.all())
    report = []

    for asset in assets:
        report.extend(evaluate_asset(asset))

    LOGGER.info(
        "Full evaluation complete: %d asset(s), %d result(s)",
        len(assets), len(report),
    )
    return report
