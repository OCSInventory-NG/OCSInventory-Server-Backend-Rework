import pytest
from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.services import AccountinfoSearch
from asset.inventory_base.models import InventoryBase
from django.contrib.contenttypes.models import ContentType

SLUG = "inventory_base.inventorybase"


def rows(response):
    """The listing is only paginated when the request asks for a limit"""
    data = response.data
    return data["results"] if isinstance(data, dict) else data


@pytest.fixture
def fields(db):
    """One config of every type the product offers"""
    configs = {}
    for key, name, datatype in (
        ("text", "TAG", "TEXT"),
        ("textarea", "Comment", "TEXTAREA"),
        ("select", "Location", "SELECT"),
        ("checkbox", "Is active ?", "CHECKBOX"),
    ):
        configs[key] = AccountinfoConfig.objects.create(
            name=name, description=name, datatype=datatype, datatarget="ASSET"
        )

    configs["yes"] = AccountinfoValue.objects.create(
        accountinfo_config=configs["checkbox"], value="Yes"
    )
    configs["no"] = AccountinfoValue.objects.create(
        accountinfo_config=configs["checkbox"], value="No"
    )
    return configs


def make_asset(name, fields, tag=None, comment=None, location=None, active=None):
    asset = InventoryBase.objects.create(name=name, osname="os", uuid=name)

    data = {}
    if tag is not None:
        data[str(fields["text"].id)] = tag
    if comment is not None:
        data[str(fields["textarea"].id)] = comment
    if location is not None:
        data[str(fields["select"].id)] = {"text": location, "value": 99}
    if active is not None:
        data[str(fields["checkbox"].id)] = [fields[active].id]

    AccountinfoData.objects.create(
        accountdata=data,
        object_slug=SLUG,
        content_type=ContentType.objects.get_for_model(InventoryBase),
        object_id=asset.id,
    )
    return asset


@pytest.mark.django_db
class TestAccountinfoSearch:
    def search(self, term):
        return AccountinfoSearch(SLUG, "ASSET").matching_object_ids(term)

    def test_a_text_field_is_reachable(self, fields):
        asset = make_asset("PC-1", fields, tag="TLS-TAB-00001")
        make_asset("PC-2", fields, tag="PAR-LAP-00002")

        assert self.search("tls-tab") == {asset.id}

    def test_a_textarea_is_reachable(self, fields):
        asset = make_asset("PC-1", fields, comment="spare machine")
        make_asset("PC-2", fields, comment="on loan")

        assert self.search("SPARE") == {asset.id}

    def test_a_select_matches_on_its_label(self, fields):
        asset = make_asset("PC-1", fields, location="Toulouse")
        make_asset("PC-2", fields, location="Bordeaux")

        assert self.search("toulouse") == {asset.id}

    def test_a_checkbox_matches_on_its_label(self, fields):
        """The blob only holds value ids, so the labels are resolved first"""
        asset = make_asset("PC-1", fields, active="yes")
        make_asset("PC-2", fields, active="no")

        assert self.search("Yes") == {asset.id}

    def test_a_term_matching_nothing_returns_nothing(self, fields):
        make_asset("PC-1", fields, tag="TLS-TAB-00001", location="Toulouse")

        assert self.search("nowhere") == set()

    def test_an_internal_value_id_is_not_matched(self, fields):
        """Searching a number must not hit the ids the blob stores"""
        make_asset("PC-1", fields, location="Toulouse")

        assert self.search("99") == set()

    def test_every_type_is_searched_at_once(self, fields):
        by_tag = make_asset("PC-1", fields, tag="shared")
        by_location = make_asset("PC-2", fields, location="shared")

        assert self.search("shared") == {by_tag.id, by_location.id}


@pytest.mark.django_db
class TestAssetListingSearch:
    def test_the_quick_search_reaches_the_displayed_columns(self, api_client, fields):
        make_asset("PC-1", fields, location="Toulouse")
        make_asset("PC-2", fields, location="Bordeaux")

        response = api_client.get(
            "/asset/bases/", {"accountinfo": "true", "search": "toulouse"}
        )

        assert [row["name"] for row in rows(response)] == ["PC-1"]

    def test_the_asset_own_fields_still_match(self, api_client, fields):
        make_asset("PC-1", fields, location="Toulouse")
        make_asset("PC-2", fields, location="Bordeaux")

        response = api_client.get(
            "/asset/bases/", {"accountinfo": "true", "search": "PC-2"}
        )

        assert [row["name"] for row in rows(response)] == ["PC-2"]

    def test_an_asset_matching_on_both_sides_appears_once(self, api_client, fields):
        make_asset("Toulouse-01", fields, location="Toulouse")

        response = api_client.get(
            "/asset/bases/", {"accountinfo": "true", "search": "toulouse"}
        )

        assert len(rows(response)) == 1

    def test_nothing_changes_when_the_columns_are_not_displayed(
        self, api_client, fields
    ):
        make_asset("PC-1", fields, location="Toulouse")

        response = api_client.get("/asset/bases/", {"search": "toulouse"})

        assert rows(response) == []


@pytest.mark.django_db
class TestAssetListingUntouched:
    """The override must stay invisible on every path it does not serve"""

    def test_a_listing_without_search_is_unchanged(self, api_client, fields):
        make_asset("PC-1", fields, location="Toulouse")
        make_asset("PC-2", fields, location="Bordeaux")

        response = api_client.get("/asset/bases/", {"accountinfo": "true"})

        assert len(rows(response)) == 2

    def test_a_term_matching_nothing_still_searches_the_asset_fields(
        self, api_client, fields
    ):
        make_asset("PC-1", fields, location="Toulouse")

        response = api_client.get(
            "/asset/bases/", {"accountinfo": "true", "search": "PC-1"}
        )

        assert [row["name"] for row in rows(response)] == ["PC-1"]

    def test_the_model_filters_still_narrow_the_result(self, api_client, fields):
        toulouse = make_asset("PC-1", fields, location="Toulouse")
        InventoryBase.objects.filter(id=toulouse.id).update(osname="Debian")
        other = make_asset("PC-2", fields, location="Toulouse")
        InventoryBase.objects.filter(id=other.id).update(osname="Windows")

        response = api_client.get(
            "/asset/bases/",
            {"accountinfo": "true", "search": "toulouse", "osname": "Debian"},
        )

        assert [row["name"] for row in rows(response)] == ["PC-1"]

    def test_ordering_still_applies(self, api_client, fields):
        make_asset("PC-B", fields, location="Toulouse")
        make_asset("PC-A", fields, location="Toulouse")

        response = api_client.get(
            "/asset/bases/",
            {"accountinfo": "true", "search": "toulouse", "ordering": "-name"},
        )

        assert [row["name"] for row in rows(response)] == ["PC-B", "PC-A"]

    def test_pagination_keeps_a_correct_count(self, api_client, fields):
        for index in range(5):
            make_asset(f"PC-{index}", fields, location="Toulouse")

        response = api_client.get(
            "/asset/bases/",
            {"accountinfo": "true", "search": "toulouse", "limit": 2},
        )

        assert response.data["count"] == 5
        assert len(response.data["results"]) == 2

    def test_data_of_another_object_type_is_ignored(self, api_client, fields):
        """A netdevice carrying the same value must not surface an asset"""
        asset = make_asset("PC-1", fields, tag="only-on-the-asset")
        AccountinfoData.objects.create(
            accountdata={str(fields["text"].id): "netdevice-only"},
            object_slug="netdevice.netdevice",
            content_type=ContentType.objects.get_for_model(InventoryBase),
            object_id=asset.id,
        )

        response = api_client.get(
            "/asset/bases/", {"accountinfo": "true", "search": "netdevice-only"}
        )

        assert rows(response) == []


@pytest.mark.django_db
class TestAssetDetailUntouched:
    """
    filter_queryset also runs on retrieve, update and destroy

    DRF filters the detail route through the same backends, so a search term
    that misses already returns 404 without this override. What matters is that
    the behaviour stays identical either way.
    """

    def test_the_detail_route_behaves_the_same_either_way(self, api_client, fields):
        asset = make_asset("PC-1", fields, location="Toulouse")
        url = f"/asset/bases/{asset.id}/"

        assert api_client.get(url).status_code == 200
        for params in (
            {"search": "nowhere"},
            {"search": "nowhere", "accountinfo": "true"},
        ):
            assert api_client.get(url, params).status_code == 404

    def test_an_asset_found_through_its_data_is_reachable_on_detail(
        self, api_client, fields
    ):
        asset = make_asset("PC-1", fields, location="Toulouse")

        response = api_client.get(
            f"/asset/bases/{asset.id}/",
            {"search": "toulouse", "accountinfo": "true"},
        )

        assert response.status_code == 200

    def test_deleting_is_not_narrowed_by_the_search(self, api_client, fields):
        asset = make_asset("PC-1", fields, location="Toulouse")

        response = api_client.delete(
            f"/asset/bases/{asset.id}/?accountinfo=true&search=toulouse"
        )

        assert response.status_code == 204
        assert not InventoryBase.objects.filter(id=asset.id).exists()

    def test_malformed_data_does_not_break_the_listing(self, api_client, fields):
        """accountdata is a free JSONField, one bad row must not fail the page"""
        make_asset("PC-1", fields, tag="findme")
        AccountinfoData.objects.create(
            accountdata="not an object",
            object_slug=SLUG,
            content_type=ContentType.objects.get_for_model(InventoryBase),
            object_id=999999,
        )

        response = api_client.get(
            "/asset/bases/", {"accountinfo": "true", "search": "findme"}
        )

        assert response.status_code == 200
        assert [row["name"] for row in rows(response)] == ["PC-1"]
