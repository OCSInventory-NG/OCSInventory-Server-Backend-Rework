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
