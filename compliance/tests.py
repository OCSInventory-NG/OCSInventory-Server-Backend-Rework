import pytest
from compliance.models import AssetEOLStatus, ComplianceResult, ComplianceRule


@pytest.mark.django_db
class TestComplianceScope:
    @pytest.fixture
    def rule(self, scope_setup):
        rule = ComplianceRule.objects.create(name="Rule", type="software", logic={})
        for asset in (scope_setup.visible, scope_setup.hidden):
            ComplianceResult.objects.create(
                asset=asset, rule=rule, status="non_compliant"
            )
            AssetEOLStatus.objects.create(asset=asset, product="debian", is_eol=True)
        return rule

    @pytest.fixture
    def scoped(self, make_scoped_user, client_for, scope_setup):
        user = make_scoped_user(
            "view_complianceresult",
            "view_asseteolstatus",
            asset_groups=[scope_setup.paris],
        )
        return client_for(user)

    def test_results_list_scope_only(self, scoped, scope_setup, rule):
        data = scoped.get("/compliance/results/").data
        assert [r["asset"] for r in data] == [scope_setup.visible.id]

    def test_asset_summary_scope_only(self, scoped, scope_setup, rule):
        data = scoped.get("/compliance/results/asset-summary/").data
        assert [s["asset"] for s in data] == [scope_setup.visible.id]

    def test_asset_summary_ignores_hidden_ids(self, scoped, scope_setup, rule):
        url = f"/compliance/results/asset-summary/?asset__in={scope_setup.hidden.id}"
        assert scoped.get(url).data == []

    def test_rule_summary_counts_visible_assets(self, scoped, rule):
        data = scoped.get("/compliance/results/rule-summary/").data
        assert [s["impacted"] for s in data if s["rule"] == rule.id] == [1]

    def test_eol_status_scope_only(self, scoped, scope_setup, rule):
        data = scoped.get("/compliance/eol-status/").data
        assert [e["asset"] for e in data] == [scope_setup.visible.id]

    def test_eol_summary_scope_only(self, scoped, scope_setup, rule):
        data = scoped.get("/compliance/eol-status/eol-summary/").data
        assert [e["asset"] for e in data] == [scope_setup.visible.id]
