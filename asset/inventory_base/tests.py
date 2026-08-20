import pytest
from accountinfo.models import AccountinfoConfig, AccountinfoData
from asset.inventory_base.models import InventoryBase
from django.contrib.contenttypes.models import ContentType
from inventory.software.models import SoftwareDictionary
from inventory.template.models import Template
from rest_framework.test import APIClient


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


def create_asset(template, **overrides):
    defaults = dict(
        name="asset-1",
        description="desc",
        serial="SER-1",
        osname="Linux",
        osversion="1",
        uuid="uuid-asset-1",
        domain="example",
        agent="agent",
        template=template,
        # avoids triggering the (unrelated) automation rule engine on save
        is_template_forced=True,
    )
    defaults.update(overrides)
    return InventoryBase.objects.create(**defaults)


@pytest.mark.django_db
class TestInventoryBaseList:
    def test_list_includes_created_asset(self, api_client, template):
        create_asset(template)

        response = api_client.get("/asset/bases/")

        assert response.status_code == 200
        uuids = [asset["uuid"] for asset in response.data]
        assert "uuid-asset-1" in uuids

    def test_list_requires_authentication(self):
        response = APIClient().get("/asset/bases/")

        assert response.status_code == 401

    def test_search_filters_by_name(self, api_client, template):
        create_asset(template, name="server-01", uuid="uuid-1")
        create_asset(template, name="laptop-02", uuid="uuid-2")

        response = api_client.get("/asset/bases/?search=server")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["name"] == "server-01"


@pytest.mark.django_db
class TestInventoryBaseCreate:
    def test_create_minimal_asset(self, api_client):
        response = api_client.post(
            "/asset/bases/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 201
        assert InventoryBase.objects.filter(uuid="uuid-asset-1").exists()

    def test_create_requires_uuid_uniqueness(self, api_client, template):
        create_asset(template)

        response = api_client.post(
            "/asset/bases/",
            {
                "name": "asset-2",
                "serial": "SER-2",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 400

    def test_create_requires_add_permission(self, make_api_client):
        client = make_api_client("view_inventorybase")

        response = client.post(
            "/asset/bases/",
            {
                "name": "asset-1",
                "serial": "SER-1",
                "osname": "Linux",
                "uuid": "uuid-asset-1",
                "is_template_forced": True,
            },
            format="json",
        )

        assert response.status_code == 403
        assert not InventoryBase.objects.filter(uuid="uuid-asset-1").exists()

    def test_full_put_without_required_fields_is_rejected(self, api_client, template):
        # http_method_names on the serializer restricts the exposed API
        # (get/post/patch/delete), but the base ModelViewSet's put() is still
        # reachable and runs full (non-partial) validation
        asset = create_asset(template)

        response = api_client.put(
            f"/asset/bases/{asset.id}/",
            {"name": "renamed"},
            format="json",
        )

        assert response.status_code == 400
        asset.refresh_from_db()
        assert asset.name == "asset-1"


@pytest.mark.django_db
class TestInventoryBaseUpdate:
    def test_patch_updates_only_given_fields(self, api_client, template):
        asset = create_asset(template)

        response = api_client.patch(
            f"/asset/bases/{asset.id}/",
            {"description": "updated description"},
            format="json",
        )

        assert response.status_code == 200
        asset.refresh_from_db()
        assert asset.name == "asset-1"
        assert asset.description == "updated description"


@pytest.mark.django_db
class TestInventoryBaseAccountinfoRepresentation:
    def test_accountinfo_included_when_requested(self, api_client, template):
        asset = create_asset(template)
        config = AccountinfoConfig.objects.create(
            name="Owner", description="", datatype="TEXT", datatarget="ASSET"
        )
        AccountinfoData.objects.create(
            object_id=asset.id,
            object_slug="inventory_base.inventorybase",
            content_type=ContentType.objects.get_for_model(InventoryBase),
            accountdata={str(config.id): "IT department"},
        )

        response = api_client.get(f"/asset/bases/{asset.id}/?accountinfo=true")

        assert response.status_code == 200
        assert response.data["accountinfo"]["Owner"] == "IT department"


@pytest.mark.django_db
class TestInventoryBaseDelete:
    def test_delete_cleans_up_software_dictionary_links(self, api_client, template):
        asset = create_asset(template)
        entry = SoftwareDictionary.objects.create(name="apache2", installation_number=1)
        entry.assets.add(asset)

        response = api_client.delete(f"/asset/bases/{asset.id}/")

        assert response.status_code == 204
        assert not SoftwareDictionary.objects.filter(id=entry.id).exists()

    def test_delete_keeps_dictionary_entry_shared_with_other_assets(
        self, api_client, template
    ):
        asset = create_asset(template)
        other_asset = create_asset(template, name="asset-2", uuid="uuid-asset-2")
        entry = SoftwareDictionary.objects.create(name="apache2", installation_number=2)
        entry.assets.add(asset, other_asset)

        response = api_client.delete(f"/asset/bases/{asset.id}/")

        assert response.status_code == 204
        entry.refresh_from_db()
        assert entry.installation_number == 1
        assert list(entry.assets.all()) == [other_asset]
