import pytest
from snmp.scanner.models import SnmpScanner


@pytest.mark.django_db
class TestSnmpScannerFilter:
    @pytest.fixture(autouse=True)
    def scanners(self, db):
        SnmpScanner.objects.create(name="aaa-other", ip="10.0.0.1")
        SnmpScanner.objects.create(name="full-test", ip="10.0.0.2")

    def test_filter_by_name(self, api_client):
        response = api_client.get(
            "/snmp/scanner/", {"name": "full-test", "expand": "*"}
        )

        assert response.status_code == 200
        assert [scanner["name"] for scanner in response.data] == ["full-test"]

    def test_filter_by_unknown_name(self, api_client):
        response = api_client.get("/snmp/scanner/", {"name": "zzz-new"})

        assert response.status_code == 200
        assert response.data == []

    def test_no_filter_lists_all_by_name(self, api_client):
        response = api_client.get("/snmp/scanner/")

        assert response.status_code == 200
        assert [scanner["name"] for scanner in response.data] == [
            "aaa-other",
            "full-test",
        ]
