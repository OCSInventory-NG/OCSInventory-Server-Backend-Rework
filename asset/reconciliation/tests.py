import pytest
from asset.inventory_base.models import InventoryBase
from asset.services import ReconciliationService
from config.models import Config
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
        srcmac="00:11:22:33:44:55",
        template=template,
        is_template_forced=True,
    )


def set_server_config(entries):
    config = Config.objects.get(name="server")
    config.value = entries
    config.save()


@pytest.mark.django_db
class TestReconciliationServiceFields:
    def test_default_reconciliation_fields_is_uuid(self):
        assert ReconciliationService.get_reconciliation_fields() == ["uuid"]

    def test_reconciliation_fields_from_config_uuid_and_name(self):
        set_server_config([{"name": "duplicate_reconciliation", "value": "uuid, name"}])

        assert ReconciliationService.get_reconciliation_fields() == ["uuid", "name"]

    def test_reconciliation_fields_from_config_uuid_and_srcmac(self):
        set_server_config(
            [{"name": "duplicate_reconciliation", "value": "uuid, srcmac"}]
        )

        assert ReconciliationService.get_reconciliation_fields() == ["uuid", "srcmac"]

    def test_unknown_configured_value_falls_back_to_uuid(self):
        set_server_config([{"name": "duplicate_reconciliation", "value": "garbage"}])

        assert ReconciliationService.get_reconciliation_fields() == ["uuid"]


@pytest.mark.django_db
class TestReconciliationServiceFilter:
    def test_get_reconciliation_filter_uses_configured_fields(self):
        set_server_config([{"name": "duplicate_reconciliation", "value": "uuid, name"}])

        filter_dict = ReconciliationService.get_reconciliation_filter(
            {"uuid": "abc", "name": "host-1"}
        )

        assert filter_dict == {"uuid": "abc", "name": "host-1"}

    def test_get_reconciliation_filter_raises_when_field_missing(self):
        set_server_config([{"name": "duplicate_reconciliation", "value": "uuid, name"}])

        with pytest.raises(ValueError):
            ReconciliationService.get_reconciliation_filter({"uuid": "abc"})


@pytest.mark.django_db
class TestReconciliationServiceLegacyFields:
    def test_default_legacy_fields_is_uuid(self):
        assert ReconciliationService.get_legacy_reconciliation_fields() == ["uuid"]

    def test_legacy_fields_from_config(self):
        set_server_config(
            [
                {
                    "name": "legacy_duplicate_reconciliation",
                    "value": ["name", "serial"],
                    "options": ["uuid", "name", "serial", "srcmac"],
                }
            ]
        )

        assert ReconciliationService.get_legacy_reconciliation_fields() == [
            "name",
            "serial",
        ]

    def test_legacy_fields_filters_out_disallowed_values(self):
        set_server_config(
            [
                {
                    "name": "legacy_duplicate_reconciliation",
                    "value": ["name", "unknown_field"],
                    "options": ["uuid", "name", "serial", "srcmac"],
                }
            ]
        )

        assert ReconciliationService.get_legacy_reconciliation_fields() == ["name"]

    def test_legacy_fields_fallback_to_uuid_when_nothing_usable(self):
        set_server_config(
            [
                {
                    "name": "legacy_duplicate_reconciliation",
                    "value": ["unknown_field"],
                    "options": ["uuid", "name", "serial", "srcmac"],
                }
            ]
        )

        assert ReconciliationService.get_legacy_reconciliation_fields() == ["uuid"]


@pytest.mark.django_db
class TestReconciliationServiceLegacyFilter:
    def test_legacy_filter_uses_configured_fields(self):
        filter_dict = ReconciliationService.get_legacy_reconciliation_filter(
            {"uuid": "abc", "name": "host-1"}, fields=["name"]
        )

        assert filter_dict == {"name": "host-1"}

    def test_legacy_filter_falls_back_to_uuid_when_value_blacklisted(self):
        filter_dict = ReconciliationService.get_legacy_reconciliation_filter(
            {"uuid": "abc", "name": ""}, fields=["name"]
        )

        assert filter_dict == {"uuid": "abc"}

    def test_legacy_filter_raises_when_uuid_fallback_also_unusable(self):
        with pytest.raises(ReconciliationService.UnusableReconciliationValue):
            ReconciliationService.get_legacy_reconciliation_filter(
                {"uuid": "", "name": ""}, fields=["name"]
            )


@pytest.mark.django_db
class TestReconciliationServiceFormatInfo:
    def test_format_reconciliation_info(self):
        info = ReconciliationService.format_reconciliation_info(
            {"uuid": "abc", "name": "host-1"}, fields=["uuid", "name"]
        )

        assert info == "(uuid=abc - name=host-1)"


@pytest.mark.django_db
class TestReconciliationView:
    def test_returns_asset_id_when_found(self, asset):
        client = APIClient()

        response = client.post(
            "/asset/reconciliation/", {"uuid": "uuid-asset-1"}, format="json"
        )

        assert response.status_code == 200
        assert response.data["id"] == asset.id

    def test_returns_false_when_not_found(self):
        client = APIClient()

        response = client.post(
            "/asset/reconciliation/", {"uuid": "does-not-exist"}, format="json"
        )

        assert response.status_code == 200
        assert response.data["id"] is False

    def test_does_not_require_authentication(self):
        client = APIClient()

        response = client.post("/asset/reconciliation/", {"uuid": "x"}, format="json")

        assert response.status_code == 200

    def test_returns_400_when_reconciliation_field_missing(self):
        set_server_config([{"name": "duplicate_reconciliation", "value": "uuid, name"}])
        client = APIClient()

        response = client.post("/asset/reconciliation/", {"uuid": "x"}, format="json")

        assert response.status_code == 400
