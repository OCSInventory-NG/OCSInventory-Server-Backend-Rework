import logging

from asset.inventory_base.models import InventoryBase
from automation.rule.jsonlogic import jsonLogic

from .context import resolver
from .models import ComplianceResult, ComplianceRule

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
            rule.id,
            rule.name,
            exc,
        )
        return ComplianceResult.STATUS_UNKNOWN, {"error": str(exc)}


def evaluate_asset(asset, rules=None):
    """
    Evaluate all enabled rules against a single asset and persist results.

    Called by the ComplianceEvaluation automation task. The evaluation context
    is built by compliance.context.ComplianceContextResolver. EOL resolution is
    a separate concern owned by compliance.eol / the EOLUpdate task; it is not
    triggered here.

    `rules` lets the caller pass the enabled ComplianceRule list once for a
    whole-fleet run (avoiding one query per asset); it is fetched here when not
    provided. Results are written with a single bulk upsert per asset.

    Returns a list of dicts {asset_id, rule_id, status} for reporting.
    """
    context = resolver.build(asset)

    if rules is None:
        rules = list(ComplianceRule.objects.filter(enabled=True))

    ComplianceResult.objects.filter(asset=asset).exclude(
        rule_id__in=[r.id for r in rules]
    ).delete()

    results = []
    report = []

    for rule in rules:
        status, detail = evaluate_rule(rule, context)
        results.append(
            ComplianceResult(asset=asset, rule=rule, status=status, detail=detail)
        )
        report.append(
            {
                "asset_id": asset.id,
                "rule_id": rule.id,
                "status": status,
            }
        )
        LOGGER.debug("Asset %s / Rule %s → %s", asset.id, rule.id, status)

    ComplianceResult.objects.bulk_create(
        results,
        update_conflicts=True,
        unique_fields=["asset", "rule"],
        update_fields=["status", "detail", "evaluated_at"],
    )

    LOGGER.info("Compliance evaluated for asset %s: %d rule(s)", asset.id, len(report))
    return report


def run_evaluation():
    """
    Evaluate all enabled rules against all assets and persist results.

    Bulk helper for re-evaluating the whole fleet (e.g. from a shell). The
    ComplianceEvaluation task iterates assets itself via evaluate_asset().

    Returns a list of dicts {asset_id, rule_id, status} for reporting.
    """
    assets = list(InventoryBase.objects.all())
    rules = list(ComplianceRule.objects.filter(enabled=True))
    report = []

    for asset in assets:
        report.extend(evaluate_asset(asset, rules))

    LOGGER.info(
        "Full evaluation complete: %d asset(s), %d result(s)",
        len(assets),
        len(report),
    )
    return report
