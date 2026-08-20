import pytest
from asset.inventory_base.models import InventoryBase
from asset.inventory_section.models import InventorySection
from asset.services import ReconciliationService
from config.models import Config
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
        assert InventorySection.objects.filter(base=asset, template_section=old_section).count() == 0
        assert InventorySection.objects.filter(base=asset, template_section=section).count() == 1

    def test_put_returns_500_when_asset_not_found(self, api_client):
        response = api_client.put(
            "/asset/collection/",
            {"name": "unknown", "serial": "x", "osname": "Linux", "uuid": "does-not-exist"},
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
        assert InventorySection.objects.filter(base=asset, template_section=other_section).count() == 1
        # new section was added
        assert InventorySection.objects.filter(base=asset, template_section=section).count() == 1

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
        assert InventorySection.objects.filter(base=asset, template_section=section).count() == 1
        inventory_section = InventorySection.objects.get(base=asset, template_section=section)
        values = {
            field.template_field.name: field.value
            for field in inventory_section.fields.all()
        }
        assert values == {"NAME": "Motherboard v2", "MEMORY": "16384"}
