import pytest
from asset.inventory_base.models import InventoryBase
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template
from rest_framework.test import APIClient


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


@pytest.fixture
def section(template):
    return Section.objects.create(name="OS", target="os", template=template)


@pytest.fixture
def asset(template):
    return InventoryBase.objects.create(
        name="asset-1",
        serial="SER-1",
        osname="Linux",
        uuid="uuid-asset-1",
        template=template,
        is_template_forced=True,
    )


@pytest.mark.django_db
class TestInventorySectionList:
    def test_list_includes_created_inventory_section(self, api_client, asset, section):
        InventorySection.objects.create(base=asset, template_section=section)

        response = api_client.get("/asset/sections/")

        assert response.status_code == 200
        assert len(response.data) == 1

    def test_list_requires_authentication(self):
        response = APIClient().get("/asset/sections/")

        assert response.status_code == 401

    def test_filter_by_base(self, api_client, asset, section, template):
        other_asset = InventoryBase.objects.create(
            name="asset-2",
            serial="SER-2",
            osname="Linux",
            uuid="uuid-asset-2",
            template=template,
            is_template_forced=True,
        )
        InventorySection.objects.create(base=asset, template_section=section)
        InventorySection.objects.create(base=other_asset, template_section=section)

        response = api_client.get(f"/asset/sections/?base={asset.id}")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["base"] == asset.id


@pytest.mark.django_db
class TestInventorySectionCreate:
    def test_create_minimal_inventory_section(self, api_client, asset, section):
        response = api_client.post(
            "/asset/sections/",
            {"base": asset.id, "template_section": section.id, "fields": []},
            format="json",
        )

        assert response.status_code == 201
        assert InventorySection.objects.filter(
            base=asset, template_section=section
        ).exists()

    def test_create_requires_add_permission(self, make_api_client, asset, section):
        client = make_api_client("view_inventorysection")

        response = client.post(
            "/asset/sections/",
            {"base": asset.id, "template_section": section.id, "fields": []},
            format="json",
        )

        assert response.status_code == 403
        assert not InventorySection.objects.filter(base=asset).exists()


@pytest.mark.django_db
class TestInventorySectionDelete:
    def test_delete_cascades_to_inventory_fields(self, api_client, asset, section):
        inventory_section = InventorySection.objects.create(
            base=asset, template_section=section
        )
        template_field = Field.objects.create(name="Name", section=section, order=1)
        InventoryField.objects.create(
            inventory_section=inventory_section,
            template_field=template_field,
            value="x",
        )

        response = api_client.delete(f"/asset/sections/{inventory_section.id}/")

        assert response.status_code == 204
        assert not InventoryField.objects.filter(
            inventory_section=inventory_section.id
        ).exists()
