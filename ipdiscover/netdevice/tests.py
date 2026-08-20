import pytest
from accountinfo.models import AccountinfoConfig, AccountinfoData, AccountinfoValue
from django.contrib.contenttypes.models import ContentType
from ipdiscover.netdevice.models import Netdevice
from ipdiscover.network.models import Network
from rest_framework.test import APIClient


@pytest.fixture
def network(db):
    return Network.objects.create(
        nettag="net-1", netid="10.0.0.0", mask="255.255.255.0"
    )


@pytest.mark.django_db
class TestNetdeviceList:
    def test_list_includes_created_netdevice(self, api_client, network):
        Netdevice.objects.create(
            ip="10.0.0.5", netname="host-1", mac="00:11:22:33:44:55", network=network
        )

        response = api_client.get("/netdevices/")

        assert response.status_code == 200
        ips = [device["ip"] for device in response.data]
        assert "10.0.0.5" in ips

    def test_list_requires_authentication(self):
        response = APIClient().get("/netdevices/")

        assert response.status_code == 401

    def test_search_filters_by_netname(self, api_client, network):
        Netdevice.objects.create(
            ip="10.0.0.5", netname="printer-1", mac="00:11:22:33:44:55", network=network
        )
        Netdevice.objects.create(
            ip="10.0.0.6", netname="laptop-1", mac="00:11:22:33:44:66", network=network
        )

        response = api_client.get("/netdevices/?search=printer")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["netname"] == "printer-1"


@pytest.mark.django_db
class TestNetdeviceCreate:
    def test_create_minimal_netdevice(self, api_client, network):
        response = api_client.post(
            "/netdevices/",
            {
                "ip": "10.0.0.5",
                "netname": "host-1",
                "mac": "00:11:22:33:44:55",
                "network": network.id,
            },
            format="json",
        )

        assert response.status_code == 201
        assert Netdevice.objects.filter(ip="10.0.0.5").exists()

    def test_create_requires_add_permission(self, make_api_client, network):
        client = make_api_client("view_netdevice")

        response = client.post(
            "/netdevices/",
            {
                "ip": "10.0.0.5",
                "netname": "host-1",
                "mac": "00:11:22:33:44:55",
                "network": network.id,
            },
            format="json",
        )

        assert response.status_code == 403
        assert not Netdevice.objects.filter(ip="10.0.0.5").exists()


@pytest.mark.django_db
class TestNetdeviceAccountinfoRepresentation:
    def test_accountinfo_omitted_by_default(self, api_client, network):
        device = Netdevice.objects.create(
            ip="10.0.0.5", netname="host-1", mac="00:11:22:33:44:55", network=network
        )

        response = api_client.get(f"/netdevices/{device.id}/")

        assert response.status_code == 200
        assert "accountinfo" not in response.data

    def test_accountinfo_included_with_text_field_when_requested(
        self, api_client, network
    ):
        device = Netdevice.objects.create(
            ip="10.0.0.5", netname="host-1", mac="00:11:22:33:44:55", network=network
        )
        config = AccountinfoConfig.objects.create(
            name="Location", description="", datatype="TEXT", datatarget="IPDISCOVER"
        )
        AccountinfoData.objects.create(
            object_id=device.id,
            object_slug="netdevice.netdevice",
            content_type=ContentType.objects.get_for_model(Netdevice),
            accountdata={str(config.id): "Server room"},
        )

        response = api_client.get(f"/netdevices/{device.id}/?accountinfo=true")

        assert response.status_code == 200
        assert response.data["accountinfo"]["Location"] == "Server room"

    def test_accountinfo_resolves_checkbox_values_by_id(self, api_client, network):
        device = Netdevice.objects.create(
            ip="10.0.0.5", netname="host-1", mac="00:11:22:33:44:55", network=network
        )
        config = AccountinfoConfig.objects.create(
            name="Tags", description="", datatype="CHECKBOX", datatarget="IPDISCOVER"
        )
        value = AccountinfoValue.objects.create(
            accountinfo_config=config, value="Critical"
        )
        AccountinfoData.objects.create(
            object_id=device.id,
            object_slug="netdevice.netdevice",
            content_type=ContentType.objects.get_for_model(Netdevice),
            accountdata={str(config.id): [value.id]},
        )

        response = api_client.get(f"/netdevices/{device.id}/?accountinfo=true")

        assert response.status_code == 200
        assert response.data["accountinfo"]["Tags"] == "Critical"


@pytest.mark.django_db
class TestNetdeviceDelete:
    def test_delete_removes_netdevice(self, api_client, network):
        device = Netdevice.objects.create(
            ip="10.0.0.5", netname="host-1", mac="00:11:22:33:44:55", network=network
        )

        response = api_client.delete(f"/netdevices/{device.id}/")

        assert response.status_code == 204
        assert not Netdevice.objects.filter(id=device.id).exists()
