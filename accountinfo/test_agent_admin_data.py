import logging

import pytest
from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.services import AgentAdminData
from asset.inventory_base.models import InventoryBase
from django.contrib.contenttypes.models import ContentType

SLUG = "inventory_base.inventorybase"
LOGGER_NAME = "test.agent_admin_data"


@pytest.fixture
def configs(db):
    """One ASSET config of every type, plus an IPDISCOVER one"""
    items = {}
    for key, name, datatype, target in (
        ("tag", "TAG", "TEXT", "ASSET"),
        ("comment", "Comment", "TEXTAREA", "ASSET"),
        ("site", "Site", "SELECT", "ASSET"),
        ("usage", "Usage", "CHECKBOX", "ASSET"),
        ("zone", "Zone", "TEXT", "IPDISCOVER"),
    ):
        items[key] = AccountinfoConfig.objects.create(
            name=name, description=name, datatype=datatype, datatarget=target
        )

    for key, config, label in (
        ("paris", "site", "Paris"),
        ("lyon", "site", "Lyon"),
        ("office", "usage", "Bureautique"),
        ("dev", "usage", "Dev"),
        ("accounting", "usage", "Compta"),
    ):
        items[key] = AccountinfoValue.objects.create(
            accountinfo_config=items[config], value=label
        )
    return items


@pytest.fixture
def asset(db):
    return InventoryBase.objects.create(name="PC-042", osname="os", uuid="uuid-042")


@pytest.fixture
def apply(asset):
    service = AgentAdminData(logging.getLogger(LOGGER_NAME))

    def _apply(admin_data):
        return service.apply(asset, admin_data)

    return _apply


def stored(asset):
    return AccountinfoData.objects.get(
        content_type=ContentType.objects.get_for_model(InventoryBase),
        object_id=asset.id,
    ).accountdata


def warnings(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == LOGGER_NAME and record.levelno == logging.WARNING
    ]


def set_data(asset, accountdata):
    AccountinfoData.objects.create(
        accountdata=accountdata,
        object_slug=SLUG,
        content_type=ContentType.objects.get_for_model(InventoryBase),
        object_id=asset.id,
    )


@pytest.mark.django_db
class TestConversion:
    def test_a_text_is_stored_stripped(self, configs, asset, apply):
        apply({"TAG": "  client1  "})

        assert stored(asset)[str(configs["tag"].id)] == "client1"

    def test_a_textarea_is_stored_as_text(self, configs, asset, apply):
        apply({"Comment": "Poste de l'accueil"})

        assert stored(asset)[str(configs["comment"].id)] == "Poste de l'accueil"

    def test_a_select_stores_its_label_and_id(self, configs, asset, apply):
        apply({"Site": "Paris"})

        assert stored(asset)[str(configs["site"].id)] == {
            "text": "Paris",
            "value": configs["paris"].id,
        }

    def test_a_select_label_ignores_case_and_keeps_the_stored_one(
        self, configs, asset, apply
    ):
        apply({"Site": " paris "})

        assert stored(asset)[str(configs["site"].id)]["text"] == "Paris"

    def test_a_checkbox_stores_the_ids_in_order_without_duplicates(
        self, configs, asset, apply
    ):
        apply({"Usage": "Dev, bureautique ,Dev"})

        assert stored(asset)[str(configs["usage"].id)] == [
            configs["dev"].id,
            configs["office"].id,
        ]

    def test_a_checkbox_keeps_the_known_labels(self, configs, asset, apply, caplog):
        apply({"Usage": "Bureautique,Inconnu"})

        assert stored(asset)[str(configs["usage"].id)] == [configs["office"].id]
        assert warnings(caplog) == [
            'Admin data ignored for device PC-042: "Inconnu" is not a value of "Usage"'
        ]

    def test_a_duplicated_label_resolves_to_the_lowest_id(self, configs, asset, apply):
        AccountinfoValue.objects.create(
            accountinfo_config=configs["site"], value="Paris"
        )

        apply({"Site": "Paris"})

        assert stored(asset)[str(configs["site"].id)]["value"] == configs["paris"].id


@pytest.mark.django_db
class TestMatching:
    def test_the_name_ignores_case(self, configs, asset, apply):
        apply({"tag": "client1"})

        assert stored(asset)[str(configs["tag"].id)] == "client1"

    def test_an_exact_name_wins_over_a_case_match(self, configs, asset, apply):
        lower = AccountinfoConfig.objects.create(
            name="tag", description="tag", datatype="TEXT", datatarget="ASSET"
        )

        apply({"tag": "lower", "TAG": "upper"})

        assert stored(asset)[str(lower.id)] == "lower"
        assert stored(asset)[str(configs["tag"].id)] == "upper"

    def test_a_name_matching_only_by_case_twice_is_ambiguous(
        self, configs, asset, apply, caplog
    ):
        AccountinfoConfig.objects.create(
            name="tag", description="tag", datatype="TEXT", datatarget="ASSET"
        )

        assert apply({"Tag": "client1"}) == []
        assert warnings(caplog) == [
            'Admin data ignored for device PC-042: ambiguous field "Tag"'
        ]

    def test_an_ipdiscover_config_is_not_reachable(self, configs, asset, apply, caplog):
        assert apply({"Zone": "A"}) == []
        assert warnings(caplog) == [
            'Admin data ignored for device PC-042: unknown field "Zone"'
        ]


@pytest.mark.django_db
class TestRejection:
    def test_unknown_field_and_unknown_label_are_logged(
        self, configs, asset, apply, caplog
    ):
        applied = apply({"Sitee": "Paris", "Site": "Marseille"})

        assert applied == []
        assert warnings(caplog) == [
            'Admin data ignored for device PC-042: unknown field "Sitee"',
            (
                "Admin data ignored for device PC-042: "
                '"Marseille" is not a value of "Site"'
            ),
        ]
        assert not AccountinfoData.objects.filter(object_id=asset.id).exists()

    def test_an_empty_text_is_rejected(self, configs, asset, apply, caplog):
        assert apply({"TAG": "   "}) == []
        assert warnings(caplog) == [
            'Admin data ignored for device PC-042: empty value for "TAG"'
        ]

    def test_a_checkbox_without_any_known_label_is_rejected(
        self, configs, asset, apply
    ):
        assert apply({"Usage": "Inconnu"}) == []

    def test_a_value_that_is_not_a_string_is_rejected(
        self, configs, asset, apply, caplog
    ):
        assert apply({"TAG": 42}) == []
        assert warnings(caplog) == [
            'Admin data ignored for device PC-042: value of "TAG" is not a string'
        ]

    def test_admin_data_that_is_not_an_object_is_rejected(
        self, configs, asset, apply, caplog
    ):
        assert apply(["TAG=client1"]) == []
        assert warnings(caplog) == [
            "Admin data ignored for device PC-042: admin_data is not an object"
        ]

    @pytest.mark.parametrize("admin_data", [None, {}])
    def test_nothing_sent_does_nothing(self, configs, asset, apply, caplog, admin_data):
        assert apply(admin_data) == []
        assert [r for r in caplog.records if r.name == LOGGER_NAME] == []
        assert not AccountinfoData.objects.filter(object_id=asset.id).exists()


@pytest.mark.django_db
class TestFilling:
    def test_a_value_set_in_the_console_is_kept(self, configs, asset, apply):
        set_data(asset, {str(configs["tag"].id): "client2"})

        assert apply({"TAG": "client1"}) == []
        assert stored(asset)[str(configs["tag"].id)] == "client2"

    def test_only_the_empty_values_are_filled(self, configs, asset, apply):
        set_data(
            asset,
            {
                str(configs["tag"].id): "client2",
                str(configs["site"].id): None,
                str(configs["usage"].id): [],
            },
        )

        applied = apply(
            {"TAG": "client1", "Site": "Lyon", "Usage": "Dev", "Comment": "neuf"}
        )

        assert applied == ["Site", "Usage", "Comment"]
        data = stored(asset)
        assert data[str(configs["tag"].id)] == "client2"
        assert data[str(configs["site"].id)]["text"] == "Lyon"
        assert data[str(configs["usage"].id)] == [configs["dev"].id]
        assert data[str(configs["comment"].id)] == "neuf"

    def test_missing_data_is_created_blank_for_every_asset_config(
        self, configs, asset, apply
    ):
        apply({"TAG": "client1"})

        assert stored(asset) == {
            str(configs["tag"].id): "client1",
            str(configs["comment"].id): "",
            str(configs["site"].id): None,
            str(configs["usage"].id): [],
        }

    def test_null_accountdata_is_filled(self, configs, asset, apply):
        set_data(asset, None)

        apply({"TAG": "client1"})

        assert stored(asset) == {str(configs["tag"].id): "client1"}

    def test_the_filled_fields_are_logged_once(self, configs, asset, apply, caplog):
        caplog.set_level(logging.INFO, logger=LOGGER_NAME)

        apply({"TAG": "client1", "Site": "Paris"})

        assert [r.getMessage() for r in caplog.records if r.name == LOGGER_NAME] == [
            "Admin data applied for device PC-042: TAG, Site"
        ]
