from datetime import timedelta

import pytest
from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from automation.tasks.dynaGroups import DynaGroups
from django.contrib.auth.models import User
from django.utils import timezone
from inventory.software.models import SoftwareDictionary
from rest_framework.test import APIClient
from search.views import SearchView
from security.asset_security import RANKS
from security.models import AssetSecurity, Exclusion, Exposure, Vulnerability


def condition(field, value, operator="icontains", obj="InventoryBase", **extra):
    return {
        "object": obj,
        "field": field,
        "operator": operator,
        "value": value,
        "fieldtype": "string",
        "link": "AND",
        **extra,
    }


def search(client, *conditions):
    return client.post("/search/", {"search_data": [list(conditions)]}, format="json")


def make_asset(name):
    return InventoryBase.objects.create(
        name=name, serial=f"S-{name}", osname="Linux", osversion="1", uuid=name
    )


def names(response):
    return sorted(row["name"] for row in response.json())


@pytest.mark.django_db
def test_the_search_needs_a_user_allowed_to_see_the_assets(make_api_client):
    make_asset("srv-01")

    assert search(APIClient(), condition("name", "srv")).status_code == 401
    assert search(make_api_client(), condition("name", "srv")).status_code == 403
    allowed = make_api_client("view_inventorybase", username="viewer")
    assert names(search(allowed, condition("name", "srv"))) == ["srv-01"]


@pytest.mark.django_db
def test_a_condition_compares_a_column_and_never_follows_a_relation(api_client):
    asset = make_asset("srv-01")
    user = User.objects.create_user(username="someone", password="secret")
    Exclusion.objects.create(asset=asset, comment="c", user=user)

    rejected = [
        # a password hash, read character after character
        condition("security_exclusions__user__password", user.password[:8]),
        condition("password", "x", obj="security_exclusions__user"),
        condition("name", "srv", operator="regex"),
        condition("name", "srv", operator="in"),
        condition("unknown", "srv"),
        condition("name__name", "x", obj="software_dictionary_entries"),
        condition("1__value", "x", obj="AccountinfoConfig"),
        condition("1", "x", obj="inventory_sections", section="1 OR 1"),
    ]
    for wrong in rejected:
        response = search(api_client, wrong)
        assert response.status_code == 400, wrong
        assert "error" in response.json()
    malformed = api_client.post("/search/", {"search_data": ["x"]}, format="json")
    assert malformed.status_code == 400


@pytest.mark.django_db
def test_searches_on_columns_and_software_still_work(api_client):
    first, second = make_asset("srv-01"), make_asset("pc-02")
    apache = SoftwareDictionary.objects.create(name="apache2", version="2.4")
    apache.assets.add(first)
    old = SoftwareDictionary.objects.create(name="apache2", version="2.2")
    old.assets.add(second)

    assert names(search(api_client, condition("name", "srv"))) == ["srv-01"]
    software = search(
        api_client,
        condition("name", "apache2", "iexact", "software_dictionary_entries"),
        condition("version", "2.4", "iexact", "software_dictionary_entries"),
    ).json()
    assert [row["name"] for row in software] == ["srv-01"]
    assert software[0]["matched"]["software_dictionary_entries"][0]["version"] == "2.4"


@pytest.mark.django_db
def test_a_dynamic_group_keeps_its_machines_when_its_search_is_refused(admin_user):
    kept = make_asset("srv-01")
    group = AssetGroup.objects.create(
        name="lab",
        user=admin_user,
        visibility="public",
        is_dynamic=True,
        search=[[condition("asset_groups__user__password", "x")]],
    )
    group.assets.add(kept)
    valid = AssetGroup.objects.create(
        name="servers",
        user=admin_user,
        visibility="public",
        is_dynamic=True,
        search=[[condition("name", "srv")]],
    )

    DynaGroups().execute()

    assert list(group.assets.all()) == [kept]
    assert list(valid.assets.all()) == [kept]


# Security criteria


NOW = timezone.now()


def vulnerability(vuln_id, score=None, rating="", kev=False):
    return Vulnerability.objects.create(
        vuln_id=vuln_id, cvss_score=score, distro_rating=rating, kev=kev
    )


def expose(asset, vuln, software="curl", fixed="", closed=False):
    return Exposure.objects.create(
        asset=asset,
        vulnerability=vuln,
        scheme="purl",
        product=f"pkg:deb/debian/{software}",
        software_name=software,
        version="1.0",
        fixed_version=fixed,
        method="osv",
        first_seen=NOW - timedelta(days=3),
        last_seen=NOW,
        closed_at=NOW if closed else None,
    )


def security(*conditions):
    return [
        {
            "object": obj,
            "field": field,
            "operator": operator,
            "value": value,
            "link": "AND",
        }
        for obj, field, operator, value in conditions
    ]


def post(client, *groups, url="/search/", **options):
    return client.post(url, {"search_data": list(groups), **options}, format="json")


@pytest.fixture
def fleet(db):
    """
    fixed: a critical CVE with a fix and a low one without;
    unfixed: the critical CVE without fix; clean: scanned, nothing open;
    new: never scanned (no stored security).
    """
    critical = vulnerability("CVE-2026-1", score=9.8, kev=True)
    low = vulnerability("CVE-2026-2", rating="low")
    machines = {name: make_asset(name) for name in ("fixed", "unfixed", "clean", "new")}
    expose(machines["fixed"], critical, fixed="8.0-2")
    expose(machines["fixed"], low, software="wget")
    expose(machines["unfixed"], critical)
    expose(machines["clean"], critical, closed=True)
    for name, status, cves, fixable in (
        ("fixed", "critical", 2, 1),
        ("unfixed", "critical", 1, 0),
        ("clean", "not_vulnerable", 0, 0),
    ):
        AssetSecurity.objects.create(
            asset=machines[name],
            status=status,
            rank=RANKS[status],
            cves=cves,
            cves_fixable=fixable,
            updated_at=NOW,
        )
    return machines


V = "vulnerabilities"


def test_the_conditions_on_vulnerabilities_match_the_same_one(api_client, fleet):
    # fixed has a critical one (with fix) and one without fix (low): not
    # the same vulnerability
    rows = post(
        api_client,
        security(
            (V, "level", "exact", "critical"), (V, "fix_available", "exact", "no")
        ),
    ).json()
    assert [row["name"] for row in rows] == ["unfixed"]
    matched = rows[0]["matched"]["vulnerabilities"]
    assert [(m["vuln_id"], m["level"], m["kev"]) for m in matched] == [
        ("CVE-2026-1", "critical", True)
    ]

    def found(*conditions):
        return names(post(api_client, security(*conditions)))

    assert found((V, "vuln_id", "iexact", "cve-2026-1")) == ["fixed", "unfixed"]
    assert found((V, "kev", "exact", True), (V, "cvss_score", "gte", 9)) == [
        "fixed",
        "unfixed",
    ]
    assert found((V, "software_name", "icontains", "wge")) == ["fixed"]
    assert found((V, "first_seen", "lte", NOW.date().isoformat())) == [
        "fixed",
        "unfixed",
    ]
    # two conditions on the same field: two vulnerabilities
    assert found((V, "level", "exact", "critical"), (V, "level", "exact", "low")) == [
        "fixed"
    ]


def test_the_exclusions_apply_to_the_search(api_client, admin_user, fleet):
    Exclusion.objects.create(asset=fleet["unfixed"], vuln_id="CVE-2026-1", comment="x")
    group = AssetGroup.objects.create(name="lab", user=admin_user, visibility="public")
    group.assets.add(fleet["fixed"])

    query = security((V, "vuln_id", "exact", "CVE-2026-1"))
    assert names(post(api_client, query)) == ["fixed"]
    Exclusion.objects.create(group=group, comment="lab")
    assert names(post(api_client, query)) == []
    # an expired one no longer applies
    Exclusion.objects.update(expires_at=NOW - timedelta(days=1))
    assert names(post(api_client, query)) == ["fixed", "unfixed"]


def test_the_machine_security_is_searched(api_client, fleet):
    def found(*conditions):
        return names(post(api_client, security(*conditions)))

    S = "security"
    assert found((S, "status", "exact", "critical")) == ["fixed", "unfixed"]
    # without stored security: not scanned, no vulnerability
    assert found((S, "status", "iexact", "NOT_SCANNED")) == ["new"]
    assert found((S, "cves", "gte", 1)) == ["fixed", "unfixed"]
    assert found((S, "cves", "lte", 0)) == ["clean", "new"]
    assert found((S, "cves_fixable", "exact", 1)) == ["fixed"]
    # with the other objects, and across groups
    either = post(
        api_client,
        security((S, "status", "exact", "not_vulnerable")),
        [{**security((V, "fix_available", "exact", "no"))[0], "link": "OR"}],
    )
    assert names(either) == ["clean", "fixed", "unfixed"]
    both = post(
        api_client,
        [condition("name", "fix", "istartswith")]
        + security((S, "status", "exact", "critical")),
    )
    assert names(both) == ["fixed"]


def test_ungrouped_rows_are_one_per_vulnerability(api_client, fleet):
    response = post(
        api_client,
        security((V, "cvss_score", "gte", 0)) + [condition("name", "fixed", "iexact")],
        url="/search/?limit=10",
        ungroup=True,
    ).json()
    # the low one has no score: not "0 or more"
    assert response["count"] == 1
    grouped = post(api_client, security((V, "level", "exact", "low"))).json()
    assert grouped[0]["matched"]["vulnerabilities_remaining_count"] == 0

    every = post(
        api_client,
        [
            {**security((V, "level", "exact", "critical"))[0], "link": "OR"},
            {**security((V, "level", "exact", "low"))[0], "link": "OR"},
        ],
        url="/search/?limit=10",
        ungroup=True,
    ).json()
    rows = [
        (row["name"], row["matched"]["vulnerabilities"][0]["vuln_id"])
        for row in every["results"]
    ]
    assert sorted(rows) == [
        ("fixed", "CVE-2026-1"),
        ("fixed", "CVE-2026-2"),
        ("unfixed", "CVE-2026-1"),
    ]


def test_the_security_criteria_need_to_see_vulnerabilities(make_api_client, fleet):
    query = security((V, "level", "exact", "critical"))
    assets_only = make_api_client("view_inventorybase")
    assert post(assets_only, query).status_code == 403
    assert post(assets_only, [condition("name", "fix")]).status_code == 200
    both = make_api_client(
        "view_inventorybase", "view_vulnerability", username="analyst"
    )
    assert names(post(both, query)) == ["fixed", "unfixed"]


@pytest.mark.parametrize(
    "wrong",
    [
        (V, "level", "exact", "urgent"),
        (V, "cvss_score", "gte", "high"),
        (V, "cvss_score", "icontains", "9"),
        (V, "kev", "exact", "maybe"),
        (V, "first_seen", "lte", "yesterday"),
        (V, "vulnerability__summary", "icontains", "x"),
        (V, "vuln_id", "regex", ".*"),
        ("security", "status", "exact", "red"),
        ("security", "cves", "icontains", "1"),
        ("security", "rank", "gte", 1),
    ],
)
def test_the_security_criteria_are_checked(api_client, wrong):
    response = post(api_client, security(wrong))
    assert response.status_code == 400
    assert response.json()["error"]


def test_a_dynamic_group_on_security_criteria(api_client, admin_user, fleet):
    group = AssetGroup.objects.create(
        name="critical",
        user=admin_user,
        visibility="public",
        is_dynamic=True,
        search=[security(("security", "status", "exact", "critical"))],
    )

    DynaGroups().execute()

    assert sorted(group.assets.values_list("name", flat=True)) == ["fixed", "unfixed"]
    # excluding it would make its machines leave it, then come back
    refused = api_client.post(
        "/vulnerability_exclusions/",
        {"group": group.id, "comment": "x"},
        format="json",
    )
    assert refused.status_code == 400
    assert "dynamic group" in refused.json()["error"]


def test_no_security_criteria_in_a_group_an_exclusion_targets(api_client, admin_user):
    group = AssetGroup.objects.create(
        name="lab",
        user=admin_user,
        visibility="public",
        is_dynamic=True,
        search=[[condition("name", "srv")]],
    )
    Exclusion.objects.create(group=group, comment="lab")

    response = api_client.patch(
        f"/asset/groups/{group.id}/",
        {"search": [security(("security", "status", "exact", "critical"))]},
        format="json",
    )
    assert response.status_code == 400
    assert "Security criteria" in str(response.json())
    assert (
        api_client.patch(
            f"/asset/groups/{group.id}/", {"name": "lab 2"}, format="json"
        ).status_code
        == 200
    )


LINUX = {
    "object": "InventoryBase",
    "field": "osname",
    "operator": "icontains",
    "value": "Linux",
    "link": "AND",
}

FIREFOX = {
    "object": "software_dictionary_entries",
    "field": "name",
    "operator": "iexact",
    "value": "firefox",
    "link": "AND",
}


def _name(value, link="AND"):
    return {
        "object": "InventoryBase",
        "field": "name",
        "operator": "iexact",
        "value": value,
        "link": link,
    }


@pytest.mark.django_db
class TestSearchScope:
    @pytest.fixture
    def scoped(self, scope_setup, make_scoped_user, client_for):
        user = make_scoped_user("view_inventorybase", asset_groups=[scope_setup.paris])
        return client_for(user)

    @pytest.fixture
    def plain(self, make_scoped_user, client_for):
        user = make_scoped_user("view_inventorybase", username="plain")
        return client_for(user)

    @pytest.fixture
    def firefox(self, scope_setup):
        entry = SoftwareDictionary.objects.create(name="firefox", installation_number=2)
        entry.assets.set([scope_setup.visible, scope_setup.hidden])
        return entry

    def test_search_returns_scope_assets_only(self, scoped, scope_setup):
        response = scoped.post("/search/", {"search_data": [[LINUX]]}, format="json")
        assert [a["id"] for a in response.data] == [scope_setup.visible.id]

    def test_ungrouped_search_returns_scope_assets_only(self, scoped, scope_setup):
        data = {"search_data": [[LINUX]], "ungroup": True}
        response = scoped.post("/search/", data, format="json")
        assert {row["id"] for row in response.data} == {scope_setup.visible.id}

    def test_or_groups_stay_in_scope(self, scoped, scope_setup):
        data = {"search_data": [[_name("visible")], [_name("hidden", link="OR")]]}
        response = scoped.post("/search/", data, format="json")
        assert [a["id"] for a in response.data] == [scope_setup.visible.id]

    def test_process_search_without_request_is_not_scoped(self, scope_setup):
        # the DynaGroups task path
        ids = set(SearchView().process_search([[LINUX]]).values_list("id", flat=True))
        assert ids == {scope_setup.visible.id, scope_setup.hidden.id}

    @pytest.mark.parametrize("ungroup", [False, True])
    def test_software_match_hides_stored_count(
        self, scoped, scope_setup, firefox, ungroup
    ):
        data = {"search_data": [[FIREFOX]], "ungroup": ungroup}
        response = scoped.post("/search/", data, format="json")
        assert [row["id"] for row in response.data] == [scope_setup.visible.id]
        match = response.data[0]["matched"]["software_dictionary_entries"][0]
        assert match["name"] == "firefox"
        assert "installation_number" not in match

    @pytest.mark.parametrize("ungroup", [False, True])
    def test_unscoped_software_match_keeps_stored_count(self, plain, firefox, ungroup):
        data = {"search_data": [[FIREFOX]], "ungroup": ungroup}
        response = plain.post("/search/", data, format="json")
        assert [
            row["matched"]["software_dictionary_entries"][0]["installation_number"]
            for row in response.data
        ] == [2, 2]
