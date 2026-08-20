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
def template_field(section):
    return Field.objects.create(name="Name", section=section, order=1)


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


@pytest.fixture
def inventory_section(asset, section):
    return InventorySection.objects.create(base=asset, template_section=section)


@pytest.mark.django_db
class TestInventoryFieldList:
    def test_list_includes_created_inventory_field(
        self, api_client, inventory_section, template_field
    ):
        InventoryField.objects.create(
            inventory_section=inventory_section,
            template_field=template_field,
            value="Linux",
        )

        response = api_client.get("/asset/fields/")

        assert response.status_code == 200
        values = [field["value"] for field in response.data]
        assert "Linux" in values

    def test_list_requires_authentication(self):
        response = APIClient().get("/asset/fields/")

        assert response.status_code == 401

    def test_filter_by_inventory_section(
        self, api_client, inventory_section, template_field
    ):
        InventoryField.objects.create(
            inventory_section=inventory_section,
            template_field=template_field,
            value="Linux",
        )

        response = api_client.get(
            f"/asset/fields/?inventory_section={inventory_section.id}"
        )

        assert response.status_code == 200
        assert len(response.data) == 1


@pytest.mark.django_db
class TestInventoryFieldCreate:
    def test_create_minimal_inventory_field(
        self, api_client, inventory_section, template_field
    ):
        response = api_client.post(
            "/asset/fields/",
            {
                "inventory_section": inventory_section.id,
                "template_field": template_field.id,
                "value": "Linux",
            },
            format="json",
        )

        assert response.status_code == 201
        assert InventoryField.objects.filter(value="Linux").exists()

    def test_create_requires_add_permission(
        self, make_api_client, inventory_section, template_field
    ):
        client = make_api_client("view_inventoryfield")

        response = client.post(
            "/asset/fields/",
            {
                "inventory_section": inventory_section.id,
                "template_field": template_field.id,
                "value": "Linux",
            },
            format="json",
        )

        assert response.status_code == 403
        assert not InventoryField.objects.filter(value="Linux").exists()


@pytest.mark.django_db
class TestInventoryFieldUpdate:
    def test_update_changes_value(self, api_client, inventory_section, template_field):
        field = InventoryField.objects.create(
            inventory_section=inventory_section,
            template_field=template_field,
            value="old",
        )

        response = api_client.put(
            f"/asset/fields/{field.id}/",
            {
                "inventory_section": inventory_section.id,
                "template_field": template_field.id,
                "value": "new",
            },
            format="json",
        )

        assert response.status_code == 200
        field.refresh_from_db()
        assert field.value == "new"


@pytest.mark.django_db
class TestInventoryFieldDelete:
    def test_delete_removes_inventory_field(
        self, api_client, inventory_section, template_field
    ):
        field = InventoryField.objects.create(
            inventory_section=inventory_section,
            template_field=template_field,
            value="Linux",
        )

        response = api_client.delete(f"/asset/fields/{field.id}/")

        assert response.status_code == 204
        assert not InventoryField.objects.filter(id=field.id).exists()
