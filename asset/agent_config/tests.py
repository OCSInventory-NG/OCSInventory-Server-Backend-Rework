import pytest
from rest_framework.test import APIClient

from config.models import Config


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
        # AgentConfigViewSet is read-only (http_method_names = ["get"]),
        # so POST must be rejected outright.
        response = api_client.post(
            "/asset/configs/",
            {"name": "custom", "value": {}},
            format="json",
        )

        assert response.status_code == 405
        assert not Config.objects.filter(name="custom").exists()
