import pytest
from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from automation.tasks.dynaGroups import DynaGroups
from django.contrib.auth.models import User
from inventory.software.models import SoftwareDictionary
from rest_framework.test import APIClient
from security.models import Exclusion


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
