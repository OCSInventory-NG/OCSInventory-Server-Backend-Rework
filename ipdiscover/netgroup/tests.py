import pytest
from ipdiscover.netgroup.models import Netgroup
from ipdiscover.network.models import Network
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestNetgroupList:
    def test_list_includes_created_netgroup(self, api_client):
        Netgroup.objects.create(name="HQ", description="Head office")

        response = api_client.get("/netgroups/")

        assert response.status_code == 200
        names = [group["name"] for group in response.data]
        assert "HQ" in names

    def test_list_requires_authentication(self):
        response = APIClient().get("/netgroups/")

        assert response.status_code == 401

    def test_expand_networks_includes_nested_network_data(self, api_client):
        group = Netgroup.objects.create(name="HQ", description="Head office")
        Network.objects.create(
            nettag="hq-net",
            name="HQ network",
            netid="10.0.0.0",
            mask="255.255.255.0",
            group=group,
        )

        response = api_client.get(f"/netgroups/{group.id}/?expand=networks")

        assert response.status_code == 200
        assert response.data["networks"][0]["nettag"] == "hq-net"


@pytest.mark.django_db
class TestNetgroupCreate:
    def test_create_minimal_netgroup(self, api_client):
        response = api_client.post(
            "/netgroups/",
            {"name": "HQ", "description": "Head office"},
            format="json",
        )

        assert response.status_code == 201
        assert Netgroup.objects.filter(name="HQ").exists()

    def test_create_requires_add_permission(self, make_api_client):
        client = make_api_client("view_netgroup")

        response = client.post(
            "/netgroups/",
            {"name": "HQ", "description": "Head office"},
            format="json",
        )

        assert response.status_code == 403
        assert not Netgroup.objects.filter(name="HQ").exists()


@pytest.mark.django_db
class TestNetgroupDelete:
    def test_delete_cascades_to_networks(self, api_client):
        group = Netgroup.objects.create(name="HQ", description="Head office")
        network = Network.objects.create(
            nettag="hq-net",
            name="HQ network",
            netid="10.0.0.0",
            mask="255.255.255.0",
            group=group,
        )

        response = api_client.delete(f"/netgroups/{group.id}/")

        assert response.status_code == 204
        assert not Network.objects.filter(id=network.id).exists()
