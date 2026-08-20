import pytest
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.netgroup.models import Netgroup
from ipdiscover.network.models import Network
from rest_framework.test import APIClient


@pytest.fixture
def netgroup(db):
    return Netgroup.objects.create(name="HQ", description="Head office")


@pytest.mark.django_db
class TestNetworkList:
    def test_list_includes_created_network(self, api_client):
        Network.objects.create(
            nettag="net-1", name="Net 1", netid="10.0.0.0", mask="255.255.255.0"
        )

        response = api_client.get("/networks/")

        assert response.status_code == 200
        tags = [net["nettag"] for net in response.data]
        assert "net-1" in tags

    def test_list_requires_authentication(self):
        response = APIClient().get("/networks/")

        assert response.status_code == 401


@pytest.mark.django_db
class TestNetworkCreate:
    def test_create_defaults_nettag_to_netid_when_not_provided(self, api_client):
        response = api_client.post(
            "/networks/",
            {
                "name": "Net 1",
                "netid": "10.0.0.0",
                "mask": "255.255.255.0",
                "netdevices": [],
            },
            format="json",
        )

        assert response.status_code == 201
        network = Network.objects.get(netid="10.0.0.0")
        assert network.nettag == "10.0.0.0"

    def test_create_keeps_explicit_nettag(self, api_client):
        response = api_client.post(
            "/networks/",
            {
                "nettag": "custom-tag",
                "name": "Net 1",
                "netid": "10.0.0.0",
                "mask": "255.255.255.0",
                "netdevices": [],
            },
            format="json",
        )

        assert response.status_code == 201
        network = Network.objects.get(netid="10.0.0.0")
        assert network.nettag == "custom-tag"

    def test_create_with_nested_netdevices(self, api_client):
        response = api_client.post(
            "/networks/",
            {
                "netid": "10.0.0.0",
                "mask": "255.255.255.0",
                "netdevices": [
                    {"ip": "10.0.0.5", "netname": "host-1", "mac": "00:11:22:33:44:55"}
                ],
            },
            format="json",
        )

        assert response.status_code == 201
        network = Network.objects.get(netid="10.0.0.0")
        assert network.netdevices.count() == 1
        assert network.netdevices.get().ip == "10.0.0.5"

    def test_create_requires_add_permission(self, make_api_client):
        client = make_api_client("view_network")

        response = client.post(
            "/networks/",
            {"netid": "10.0.0.0", "mask": "255.255.255.0", "netdevices": []},
            format="json",
        )

        assert response.status_code == 403
        assert not Network.objects.filter(netid="10.0.0.0").exists()


@pytest.mark.django_db
class TestNetworkUpdate:
    def test_update_preserves_name_when_omitted(self, api_client, netgroup):
        network = Network.objects.create(
            nettag="net-1",
            name="Custom name",
            netid="10.0.0.0",
            mask="255.255.255.0",
        )

        response = api_client.put(
            f"/networks/{network.id}/",
            {"netid": "10.0.0.0", "mask": "255.255.255.0", "netdevices": []},
            format="json",
        )

        assert response.status_code == 200
        network.refresh_from_db()
        assert network.name == "Custom name"

    def test_update_overwrites_name_when_it_still_equals_netid(self, api_client):
        network = Network.objects.create(
            nettag="net-1",
            name="10.0.0.0",
            netid="10.0.0.0",
            mask="255.255.255.0",
        )

        response = api_client.put(
            f"/networks/{network.id}/",
            {
                "netid": "10.0.0.0",
                "mask": "255.255.255.0",
                "name": "New name",
                "netdevices": [],
            },
            format="json",
        )

        assert response.status_code == 200
        network.refresh_from_db()
        assert network.name == "New name"

    def test_update_upserts_existing_netdevice_by_ip(self, api_client):
        network = Network.objects.create(
            nettag="net-1", netid="10.0.0.0", mask="255.255.255.0"
        )
        Netdevice.objects.create(
            ip="10.0.0.5", netname="old-name", mac="00:00:00:00:00:00", network=network
        )

        response = api_client.put(
            f"/networks/{network.id}/",
            {
                "netid": "10.0.0.0",
                "mask": "255.255.255.0",
                "netdevices": [
                    {
                        "ip": "10.0.0.5",
                        "netname": "new-name",
                        "mac": "11:11:11:11:11:11",
                    }
                ],
            },
            format="json",
        )

        assert response.status_code == 200
        assert Netdevice.objects.filter(network=network).count() == 1
        device = Netdevice.objects.get(network=network)
        assert device.netname == "new-name"
        assert device.mac == "11:11:11:11:11:11"

    def test_update_creates_new_netdevice_when_ip_not_found(self, api_client):
        network = Network.objects.create(
            nettag="net-1", netid="10.0.0.0", mask="255.255.255.0"
        )

        response = api_client.put(
            f"/networks/{network.id}/",
            {
                "netid": "10.0.0.0",
                "mask": "255.255.255.0",
                "netdevices": [
                    {"ip": "10.0.0.9", "netname": "host-9", "mac": "22:22:22:22:22:22"}
                ],
            },
            format="json",
        )

        assert response.status_code == 200
        assert Netdevice.objects.filter(network=network, ip="10.0.0.9").exists()


@pytest.mark.django_db
class TestNetworkDelete:
    def test_delete_cascades_to_netdevices(self, api_client):
        network = Network.objects.create(
            nettag="net-1", netid="10.0.0.0", mask="255.255.255.0"
        )
        device = Netdevice.objects.create(
            ip="10.0.0.5", netname="host", mac="00:11:22:33:44:55", network=network
        )

        response = api_client.delete(f"/networks/{network.id}/")

        assert response.status_code == 204
        assert not Netdevice.objects.filter(id=device.id).exists()
