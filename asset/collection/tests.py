import logging

import pytest
from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from accountinfo.services import AgentAdminData
from asset.collection.views import CollectionView
from asset.inventory_base.models import InventoryBase
from asset.inventory_section.models import InventorySection
from asset.services import ReconciliationService
from config.models import Config
from django.contrib.contenttypes.models import ContentType
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


@pytest.fixture
def section(template):
    return Section.objects.create(name="HARDWARE", target="hardware", template=template)


@pytest.fixture
def hardware_fields(section):
    return {
        "name": Field.objects.create(name="NAME", section=section, order=1),
        "memory": Field.objects.create(name="MEMORY", section=section, order=2),
    }


def enable_blacklist_switch(name, value):
    config = Config.objects.get(name="blacklist")
    for group in config.value:
        if group[0]["name"] == name:
            group[0]["value"] = True
            group[1]["value"] = value
    config.save()


@pytest.fixture(autouse=True)
def force_agent_uuid_reconciliation(db):
    """
    Keeps reconciliation on plain uuid lookup for these tests: the collection
    endpoint always calls ReconciliationService, and its default fields are
    already ["uuid"], so this fixture only documents that assumption.
    """
    assert ReconciliationService.get_reconciliation_fields() == ["uuid"]


class TestSanitizeFieldValue:
    def test_strips_nul_characters(self):
        nul = chr(0)
        value = f"2.0.56{nul * 5}"

        assert CollectionView.sanitize_field_value(value) == "2.0.56"

    def test_strips_lone_utf16_surrogates(self):
        lone_surrogate = chr(0xD800)
        value = f"abc{lone_surrogate}def"

        sanitized = CollectionView.sanitize_field_value(value)

        assert sanitized == "abcdef"
        # a lone surrogate would otherwise blow up UTF-8 encoding on the
        # way to the DB driver
        sanitized.encode("utf-8")

    def test_recurses_into_lists_and_dicts(self):
        nul = chr(0)
        value = {"a": [f"x{nul}y", {"b": f"z{nul}"}]}

        assert CollectionView.sanitize_field_value(value) == {"a": ["xy", {"b": "z"}]}

    def test_leaves_non_string_values_unchanged(self):
        assert CollectionView.sanitize_field_value(42) == 42
        assert CollectionView.sanitize_field_value(None) is None
        assert CollectionView.sanitize_field_value(True) is True


@pytest.mark.django_db
class TestCollectionViewCreate:
    def test_create_minimal_asset(self, api_client, template):
        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 201
        assert InventoryBase.objects.filter(uuid="uuid-asset-1").exists()

    def test_create_with_template_inventory_creates_sections_and_fields(
        self, api_client, template, section, hardware_fields
    ):
        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [{"NAME": "Motherboard", "MEMORY": "16384"}]
                },
            },
            format="json",
        )

        assert response.status_code == 201
        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        inventory_section = InventorySection.objects.get(base=asset)
        values = {
            field.template_field.name: field.value
            for field in inventory_section.fields.all()
        }
        assert values == {"NAME": "Motherboard", "MEMORY": "16384"}

    def test_create_strips_nul_characters_from_field_values(
        self, api_client, template, section, hardware_fields
    ):
        nul = chr(0)
        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [
                        {
                            "NAME": f"FUJIFILM Network Scanner Utility 3{nul}{nul}B",
                            "MEMORY": f"2.0.56{nul * 5}",
                        }
                    ]
                },
            },
            format="json",
        )

        assert response.status_code == 201
        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        inventory_section = InventorySection.objects.get(base=asset)
        values = {
            field.template_field.name: field.value
            for field in inventory_section.fields.all()
        }
        assert values == {
            "NAME": "FUJIFILM Network Scanner Utility 3B",
            "MEMORY": "2.0.56",
        }

    def test_create_with_unknown_section_returns_201_with_errors(
        self, api_client, template
    ):
        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {"UNKNOWN_SECTION": [{"NAME": "x"}]},
            },
            format="json",
        )

        assert response.status_code == 201
        assert InventoryBase.objects.filter(uuid="uuid-asset-1").exists()
        assert InventorySection.objects.count() == 0

    def test_create_ignores_inactive_section(
        self, api_client, template, section, hardware_fields
    ):
        section.is_active = False
        section.save()

        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [{"NAME": "Motherboard", "MEMORY": "16384"}]
                },
            },
            format="json",
        )

        assert response.status_code == 201
        assert InventoryBase.objects.filter(uuid="uuid-asset-1").exists()
        assert InventorySection.objects.count() == 0

    def test_create_rejects_blacklisted_mac_address(self, api_client, template):
        enable_blacklist_switch("macaddresses", "00:11:22:33:44:55")

        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "srcmac": "00:11:22:33:44:55",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 403
        assert not InventoryBase.objects.filter(uuid="uuid-asset-1").exists()

    def test_create_rejects_blacklisted_ip_in_cidr_range(self, api_client, template):
        enable_blacklist_switch("ipaddresses", "10.0.0.0/24")

        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "srcip": "10.0.0.42",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 403
        assert not InventoryBase.objects.filter(uuid="uuid-asset-1").exists()

    def test_create_rejects_blacklisted_serial(self, api_client, template):
        enable_blacklist_switch("serialnumbers", "BLOCKED-SERIAL")

        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "BLOCKED-SERIAL",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 403
        assert not InventoryBase.objects.filter(uuid="uuid-asset-1").exists()

    def test_create_allows_non_blacklisted_mac(self, api_client, template):
        enable_blacklist_switch("macaddresses", "AA:AA:AA:AA:AA:AA")

        response = api_client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "srcmac": "00:11:22:33:44:55",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 201

    def test_create_requires_add_permission(self, make_api_client, template):
        client = make_api_client("view_inventorybase")

        response = client.post(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 403
        assert not InventoryBase.objects.filter(uuid="uuid-asset-1").exists()


@pytest.mark.django_db
class TestCollectionViewUpdate:
    def test_put_overwrites_existing_template_inventory(
        self, api_client, template, section, hardware_fields
    ):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        old_section = Section.objects.create(
            name="OLD", target="old", template=template
        )
        InventorySection.objects.create(base=asset, template_section=old_section)

        response = api_client.put(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [{"NAME": "Motherboard", "MEMORY": "16384"}]
                },
            },
            format="json",
        )

        assert response.status_code == 200
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=old_section
            ).count()
            == 0
        )
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=section
            ).count()
            == 1
        )

    def test_put_ignores_inactive_section(
        self, api_client, template, section, hardware_fields
    ):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        section.is_active = False
        section.save()

        response = api_client.put(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [{"NAME": "Motherboard", "MEMORY": "16384"}]
                },
            },
            format="json",
        )

        assert response.status_code == 200
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=section
            ).count()
            == 0
        )

    def test_put_returns_500_when_asset_not_found(self, api_client):
        response = api_client.put(
            "/asset/collection/",
            {
                "name": "unknown",
                "serial": "x",
                "osname": "Linux",
                "uuid": "does-not-exist",
            },
            format="json",
        )

        assert response.status_code == 500
        assert not InventoryBase.objects.filter(uuid="does-not-exist").exists()

    def test_put_rejects_blacklisted_device(self, api_client, template):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        enable_blacklist_switch("serialnumbers", "SER-1")

        response = api_client.put(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 403
        asset.refresh_from_db()
        assert asset.name == "asset-1"


@pytest.mark.django_db
class TestCollectionViewPatch:
    def test_patch_only_updates_the_provided_section(
        self, api_client, template, section, hardware_fields
    ):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        other_section = Section.objects.create(
            name="SOFTWARE", target="software", template=template
        )
        InventorySection.objects.create(base=asset, template_section=other_section)

        response = api_client.patch(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [{"NAME": "Motherboard", "MEMORY": "16384"}]
                },
            },
            format="json",
        )

        assert response.status_code == 200
        # untouched section is preserved
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=other_section
            ).count()
            == 1
        )
        # new section was added
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=section
            ).count()
            == 1
        )

    def test_patch_ignores_inactive_section(
        self, api_client, template, section, hardware_fields
    ):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        section.is_active = False
        section.save()

        response = api_client.patch(
            "/asset/collection/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "template": template.id,
                "is_template_forced": True,
                "template_inventory": {
                    "HARDWARE": [{"NAME": "Motherboard", "MEMORY": "16384"}]
                },
            },
            format="json",
        )

        assert response.status_code == 200
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=section
            ).count()
            == 0
        )

    def test_patch_replaces_items_for_same_section_on_repeated_calls(
        self, api_client, template, section, hardware_fields
    ):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        payload = {
            "name": "asset-1",
            "serial": "SER-1",
            "osname": "Linux",
            "uuid": "uuid-asset-1",
            "template": template.id,
            "is_template_forced": True,
            "template_inventory": {
                "HARDWARE": [{"NAME": "Motherboard v1", "MEMORY": "8192"}]
            },
        }
        api_client.patch("/asset/collection/", payload, format="json")

        payload["template_inventory"] = {
            "HARDWARE": [{"NAME": "Motherboard v2", "MEMORY": "16384"}]
        }
        response = api_client.patch("/asset/collection/", payload, format="json")

        assert response.status_code == 200
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=section
            ).count()
            == 1
        )
        inventory_section = InventorySection.objects.get(
            base=asset, template_section=section
        )
        values = {
            field.template_field.name: field.value
            for field in inventory_section.fields.all()
        }
        assert values == {"NAME": "Motherboard v2", "MEMORY": "16384"}


COLLECTION_LOGGER = "asset.collection.views"


def set_admin_data_generation(mode):
    config = Config.objects.get(name="server")
    for item in config.value:
        if item["name"] == "admin_data_generation":
            item["value"] = mode
    config.save()


@pytest.fixture
def admin_fields(db):
    tag = AccountinfoConfig.objects.create(
        name="TAG", description="TAG", datatype="TEXT", datatarget="ASSET"
    )
    site = AccountinfoConfig.objects.create(
        name="Site", description="Site", datatype="SELECT", datatarget="ASSET"
    )
    paris = AccountinfoValue.objects.create(accountinfo_config=site, value="Paris")
    return {"tag": str(tag.id), "site": str(site.id), "paris": paris.id}


@pytest.fixture
def collection_log(caplog):
    """The collection logger does not propagate: capture it directly"""
    logger = logging.getLogger(COLLECTION_LOGGER)
    logger.addHandler(caplog.handler)
    yield caplog
    logger.removeHandler(caplog.handler)


def collection_payload(template, **extra):
    return {
        "name": "asset-1",
        "serial": "SER-1",
        "osname": "Linux",
        "uuid": "uuid-asset-1",
        "template": template.id,
        "is_template_forced": True,
        **extra,
    }


def existing_asset(template):
    return InventoryBase.objects.create(
        name="asset-1",
        serial="SER-1",
        osname="Linux",
        uuid="uuid-asset-1",
        template=template,
        is_template_forced=True,
    )


def admin_values():
    asset = InventoryBase.objects.get(uuid="uuid-asset-1")
    return AccountinfoData.objects.get(
        content_type=ContentType.objects.get_for_model(InventoryBase),
        object_id=asset.id,
    ).accountdata


def collection_messages(caplog, level):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == COLLECTION_LOGGER and record.levelno == level
    ]


class TestCollectionViewAdminData:
    def test_post_fills_the_admin_data(self, api_client, template, admin_fields):
        response = api_client.post(
            "/asset/collection/",
            collection_payload(
                template, admin_data={"TAG": "client1", "Site": "Paris"}
            ),
            format="json",
        )

        assert response.status_code == 201
        assert admin_values() == {
            admin_fields["tag"]: "client1",
            admin_fields["site"]: {"text": "Paris", "value": admin_fields["paris"]},
        }

    def test_post_without_admin_data_is_unchanged(
        self, api_client, template, admin_fields
    ):
        response = api_client.post(
            "/asset/collection/", collection_payload(template), format="json"
        )

        assert response.status_code == 201
        assert admin_values() == {admin_fields["tag"]: "", admin_fields["site"]: None}

    def test_ignored_values_are_logged_and_the_inventory_accepted(
        self, api_client, template, admin_fields, collection_log
    ):
        response = api_client.post(
            "/asset/collection/",
            collection_payload(
                template, admin_data={"Sitee": "Paris", "Site": "Marseille"}
            ),
            format="json",
        )

        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        assert response.status_code == 201
        assert response.data == {
            "message": "Inventory created successfully",
            "id": asset.id,
        }
        assert collection_messages(collection_log, logging.WARNING) == [
            'Admin data ignored for device asset-1: unknown field "Sitee"',
            (
                "Admin data ignored for device asset-1: "
                '"Marseille" is not a value of "Site"'
            ),
        ]
        assert admin_values() == {admin_fields["tag"]: "", admin_fields["site"]: None}

    def test_post_in_automation_mode_creates_the_data(
        self, api_client, template, admin_fields
    ):
        set_admin_data_generation("automation")

        response = api_client.post(
            "/asset/collection/",
            collection_payload(template, admin_data={"TAG": "client1"}),
            format="json",
        )

        assert response.status_code == 201
        assert admin_values() == {
            admin_fields["tag"]: "client1",
            admin_fields["site"]: None,
        }

    def test_put_keeps_a_value_set_in_the_console(
        self, api_client, template, admin_fields
    ):
        asset = existing_asset(template)
        AccountinfoData.objects.create(
            accountdata={admin_fields["tag"]: "client2", admin_fields["site"]: None},
            object_slug="inventory_base.inventorybase",
            content_type=ContentType.objects.get_for_model(InventoryBase),
            object_id=asset.id,
        )

        response = api_client.put(
            "/asset/collection/",
            collection_payload(
                template, admin_data={"TAG": "client1", "Site": "Paris"}
            ),
            format="json",
        )

        assert response.status_code == 200
        assert admin_values() == {
            admin_fields["tag"]: "client2",
            admin_fields["site"]: {"text": "Paris", "value": admin_fields["paris"]},
        }

    def test_patch_fills_the_admin_data(self, api_client, template, admin_fields):
        existing_asset(template)

        response = api_client.patch(
            "/asset/collection/",
            collection_payload(template, admin_data={"tag": "client1"}),
            format="json",
        )

        assert response.status_code == 200
        assert admin_values()[admin_fields["tag"]] == "client1"

    def test_malformed_admin_data_never_fails_the_inventory(
        self, api_client, template, admin_fields, collection_log
    ):
        response = api_client.post(
            "/asset/collection/",
            collection_payload(template, admin_data="TAG=client1"),
            format="json",
        )

        assert response.status_code == 201
        assert collection_messages(collection_log, logging.WARNING) == [
            "Admin data ignored for device asset-1: admin_data is not an object"
        ]

    def test_an_error_while_applying_never_fails_the_inventory(
        self, api_client, template, admin_fields, collection_log, monkeypatch
    ):
        def fail(self, asset, admin_data):
            raise RuntimeError("boom")

        monkeypatch.setattr(AgentAdminData, "apply", fail)

        response = api_client.post(
            "/asset/collection/",
            collection_payload(template, admin_data={"TAG": "client1"}),
            format="json",
        )

        assert response.status_code == 201
        assert collection_messages(collection_log, logging.ERROR) == [
            "Error while applying admin data for device asset-1: boom"
        ]

    def test_a_form_request_is_still_accepted(self, api_client, template):
        """Form data is an immutable QueryDict: admin_data must not be popped"""
        response = api_client.post(
            "/asset/collection/", collection_payload(template), format="multipart"
        )

        assert response.status_code == 201
