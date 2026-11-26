import pytest
from compliance.engine import evaluate_asset
from compliance.models import AssetEOLStatus, ComplianceResult, ComplianceRule
from inventory.software.models import SoftwareDictionary


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


@pytest.mark.django_db
class TestSoftwareVersionRule:
    @pytest.mark.parametrize(
        "installed, operator, required, expected",
        [
            (["2.8.90.0"], ">=", "2.8.53.0", "compliant"),
            (["2.8.100.0"], ">=", "2.8.53.0", "compliant"),
            (["2.10"], ">=", "2.8", "compliant"),
            # lowest installed version is the one checked
            (["2.8.10.0", "2.8.90.0"], ">=", "2.8.53.0", "non_compliant"),
            (["2.8.90.0"], "<", "2.8.53.0", "non_compliant"),
            (["2.8.90.0"], "==", "2.8.90", "compliant"),
            ([], ">=", "2.8.53.0", "non_compliant"),
        ],
    )
    def test_version_rule(self, make_asset, installed, operator, required, expected):
        asset = make_asset("pc")
        for version in installed:
            software = SoftwareDictionary.objects.create(
                name="TightVNC", version=version, major_version=version.split(".")[0]
            )
            software.assets.add(asset)
        # var path as saved by the rule editor, name in its original case
        rule = ComplianceRule.objects.create(
            name="TightVNC version",
            type="software",
            logic={
                operator: [{"var": "softwares.versions.TightVNC"}, required],
                "case_sensitive": False,
            },
        )

        evaluate_asset(asset, [rule])

        assert ComplianceResult.objects.get(asset=asset, rule=rule).status == expected
