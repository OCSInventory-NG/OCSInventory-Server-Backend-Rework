import pytest
from asset.inventory_base.models import InventoryBase
from asset.log.models import Log
from inventory.template.models import Template
from rest_framework.test import APIClient


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


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
class TestLogList:
    def test_list_includes_created_log(self, api_client, asset):
        Log.objects.create(asset=asset, scope="INVENTORY_BASE_INSERT", comment="new asset")

        response = api_client.get("/asset/logs/")

        assert response.status_code == 200
        comments = [log["comment"] for log in response.data]
        assert "new asset" in comments

    def test_list_requires_authentication(self):
        response = APIClient().get("/asset/logs/")

        assert response.status_code == 401

    def test_search_filters_by_scope(self, api_client, asset):
        Log.objects.create(asset=asset, scope="DEPLOYMENT_ERR", comment="failed deploy")
        Log.objects.create(asset=asset, scope="CONFIG_UPDATE", comment="config changed")

        response = api_client.get("/asset/logs/?search=DEPLOYMENT_ERR")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["comment"] == "failed deploy"


@pytest.mark.django_db
class TestLogCreate:
    def test_create_minimal_log(self, api_client, asset):
        response = api_client.post(
            "/asset/logs/",
            {"asset": asset.id, "scope": "TEMPLATE_UPDATE", "comment": "template changed"},
            format="json",
        )

        assert response.status_code == 201
        assert Log.objects.filter(comment="template changed").exists()

    def test_create_requires_add_permission(self, make_api_client, asset):
        client = make_api_client("view_log")

        response = client.post(
            "/asset/logs/",
            {"asset": asset.id, "scope": "TEMPLATE_UPDATE", "comment": "template changed"},
            format="json",
        )

        assert response.status_code == 403
        assert not Log.objects.filter(comment="template changed").exists()


@pytest.mark.django_db
class TestLogMethodRestrictions:
    def test_get_detail_is_allowed(self, api_client, asset):
        # http_method_names = ["get", "post"] on the serializer only limits
        # the routed actions declared for the API schema; the underlying
        # ModelViewSet's delete()/put() remain reachable regardless
        log = Log.objects.create(asset=asset, scope="UNKNOWN", comment="x")

        response = api_client.get(f"/asset/logs/{log.id}/")

        assert response.status_code == 200
        assert response.data["comment"] == "x"
