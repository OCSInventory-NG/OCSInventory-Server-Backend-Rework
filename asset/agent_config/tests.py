import pytest
from config.models import Config
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAgentConfigList:
    def test_list_only_returns_agent_and_deployment_configs(self, api_client):
        response = api_client.get("/asset/configs/")

        assert response.status_code == 200
        names = {item["name"] for item in response.data}
        assert names == {"agent", "deployment"}

    def test_list_requires_authentication(self):
        response = APIClient().get("/asset/configs/")

        assert response.status_code == 401

    def test_list_excludes_other_configs(self, api_client):
        response = api_client.get("/asset/configs/")

        names = {item["name"] for item in response.data}
        assert "server" not in names


@pytest.mark.django_db
class TestAgentConfigMethodRestrictions:
    def test_create_is_rejected(self, api_client):
        # allowed_methods = ["GET"] on AgentConfigViewSet is not a real DRF
        # method restriction (that would be http_method_names); POST still
        # reaches OCSViewSet.create(), which fails because no
        # serializer_class is defined on this read-only viewset
        response = api_client.post(
            "/asset/configs/",
            {"name": "custom", "value": {}},
            format="json",
        )

        assert response.status_code == 400
        assert not Config.objects.filter(name="custom").exists()
