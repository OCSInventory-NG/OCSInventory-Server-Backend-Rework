import io
import zlib

import pytest
from asset.inventory_base.models import InventoryBase
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from asset.legacy.parsers import LegacyXMLParser
from automation.rule.models import Action, Rule
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template
from rest_framework.test import APIClient


def compress_xml(xml_body):
    return zlib.compress(xml_body.encode("utf-8"))


PROLOG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<REQUEST>
  <QUERY>PROLOG</QUERY>
  <DEVICEID>uuid-asset-1</DEVICEID>
</REQUEST>
"""


def inventory_xml(uuid="uuid-asset-1", name="asset-1", serial="SER-1", osname="Linux"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<REQUEST>
  <QUERY>INVENTORY</QUERY>
  <DEVICEID>{uuid}</DEVICEID>
  <CONTENT>
    <HARDWARE>
      <NAME>{name}</NAME>
      <DESCRIPTION>desc</DESCRIPTION>
      <OSNAME>{osname}</OSNAME>
      <OSVERSION>1</OSVERSION>
      <IPADDR>10.0.0.5/24</IPADDR>
      <DNS>example.com</DNS>
    </HARDWARE>
    <BIOS>
      <SSN>{serial}</SSN>
    </BIOS>
    <NETWORKS>
      <STATUS>Up</STATUS>
      <MACADDR>00:11:22:33:44:55</MACADDR>
    </NETWORKS>
  </CONTENT>
</REQUEST>
"""


@pytest.fixture
def template(db):
    """
    A template auto-assigned to any inventory carrying the "Linux" osname:
    the legacy protocol never sends a template id, so InventoryBase always
    goes through the (unrelated) automation rule engine to get one assigned.
    A dedicated test-only rule keeps this test independent from the app's
    default osname rules (which only match distro-specific strings).
    """
    template = Template.objects.create(name="Legacy template", os="LEG")
    rule = Rule.objects.create(
        trigger="inventory_received",
        priority=100,
        logic={"regex": [{"var": "osname"}, "(?i)(Linux)"]},
        enabled=True,
        description="test-only: assign Legacy template to Linux assets",
    )
    Action.objects.create(
        rule=rule, priority=1, action="set", field="template", value=template.id
    )
    return template


@pytest.fixture
def section(template):
    return Section.objects.create(name="HARDWARE", target="hardware", template=template)


@pytest.fixture
def hardware_fields(section):
    return {
        "name": Field.objects.create(
            name="NAME", retrieval_value="NAME", section=section, order=1
        ),
    }


@pytest.mark.django_db
class TestLegacyXMLParserUnit:
    def test_parses_prolog_query_without_hardware_fields(self):
        parser = LegacyXMLParser()
        stream = io.BytesIO(compress_xml(PROLOG_XML))

        data = parser.parse(stream, parser_context={"request": None})

        assert data["query"] == "PROLOG"
        assert "name" not in data

    def test_parses_inventory_query_extracts_hardware_fields(self):
        class FakeRequest:
            META = {"HTTP_USER_AGENT": "OCS-Agent"}

        parser = LegacyXMLParser()
        stream = io.BytesIO(compress_xml(inventory_xml()))

        data = parser.parse(stream, parser_context={"request": FakeRequest()})

        assert data["query"] == "INVENTORY"
        assert data["name"] == "asset-1"
        assert data["serial"] == "SER-1"
        assert data["uuid"] == "uuid-asset-1"
        assert data["srcip"] == "10.0.0.5"
        assert data["srcmac"] == "00:11:22:33:44:55"
        assert data["agent"] == "OCS-Agent"

    def test_get_first_up_network_mac_skips_down_interfaces(self):
        parser = LegacyXMLParser()
        networks = [
            {"STATUS": "Down", "MACADDR": "AA:AA:AA:AA:AA:AA"},
            {"STATUS": "Up", "MACADDR": "BB:BB:BB:BB:BB:BB"},
        ]

        assert parser.get_first_up_network_mac(networks) == "BB:BB:BB:BB:BB:BB"

    def test_get_first_up_network_mac_defaults_to_empty(self):
        parser = LegacyXMLParser()

        assert parser.get_first_up_network_mac([]) == "Empty"


@pytest.mark.django_db
class TestLegacyViewProlog:
    def test_prolog_returns_send_response_without_creating_asset(self):
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(PROLOG_XML),
            content_type="application/x-compress",
        )

        assert response.status_code == 200
        assert InventoryBase.objects.count() == 0

    def test_does_not_require_authentication(self):
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(PROLOG_XML),
            content_type="application/x-compress",
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestLegacyViewCreate:
    def test_creates_asset_from_inventory_query(self, template):
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(inventory_xml()),
            content_type="application/x-compress",
        )

        assert response.status_code == 201
        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        assert asset.name == "asset-1"
        assert asset.serial == "SER-1"
        assert asset.srcmac == "00:11:22:33:44:55"

    def test_creates_sections_from_template_inventory(
        self, template, section, hardware_fields
    ):
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(inventory_xml()),
            content_type="application/x-compress",
        )

        assert response.status_code == 201
        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        inventory_section = InventorySection.objects.get(
            base=asset, template_section=section
        )
        field = InventoryField.objects.get(inventory_section=inventory_section)
        assert field.value == "asset-1"

    def test_ignores_inactive_section(self, template, section, hardware_fields):
        section.is_active = False
        section.save()
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(inventory_xml()),
            content_type="application/x-compress",
        )

        assert response.status_code == 201
        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        assert InventorySection.objects.filter(base=asset).count() == 0


@pytest.mark.django_db
class TestLegacyViewUpdate:
    def test_updates_existing_asset_matched_by_uuid(self, template):
        InventoryBase.objects.create(
            name="old-name",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(inventory_xml(name="new-name")),
            content_type="application/x-compress",
        )

        assert response.status_code == 200
        asset = InventoryBase.objects.get(uuid="uuid-asset-1")
        assert asset.name == "new-name"

    def test_update_replaces_section_items(self, template, section, hardware_fields):
        asset = InventoryBase.objects.create(
            name="asset-1",
            serial="SER-1",
            osname="Linux",
            uuid="uuid-asset-1",
            template=template,
            is_template_forced=True,
        )
        InventorySection.objects.create(base=asset, template_section=section)
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(inventory_xml(name="updated-name")),
            content_type="application/x-compress",
        )

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
        field = InventoryField.objects.get(inventory_section=inventory_section)
        assert field.value == "updated-name"

    def test_update_ignores_inactive_section(self, template, section, hardware_fields):
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
        client = APIClient()

        response = client.post(
            "/asset/legacy/",
            data=compress_xml(inventory_xml(name="updated-name")),
            content_type="application/x-compress",
        )

        assert response.status_code == 200
        assert (
            InventorySection.objects.filter(
                base=asset, template_section=section
            ).count()
            == 0
        )
