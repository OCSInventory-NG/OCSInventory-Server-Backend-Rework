import pytest
from asset.inventory_base.models import InventoryBase
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from asset.log.models import Log
from deployment.result.models import Result
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


@pytest.fixture
def scoped(make_scoped_user, client_for, scope_setup):
    user = make_scoped_user(
        "view_inventorybase",
        "add_inventorybase",
        "delete_inventorybase",
        "view_inventorysection",
        "view_inventoryfield",
        "view_log",
        "view_result",
        asset_groups=[scope_setup.paris],
    )
    return client_for(user)


@pytest.fixture
def sections(scope_setup):
    template = Template.objects.create(name="Linux", os="DEB")
    section = Section.objects.create(name="OS", target="os", template=template)
    field = Field.objects.create(name="Name", section=section, order=1)
    created = {}
    for asset in (scope_setup.visible, scope_setup.hidden):
        inventory_section = InventorySection.objects.create(
            base=asset, template_section=section
        )
        InventoryField.objects.create(
            inventory_section=inventory_section, template_field=field, value="x"
        )
        created[asset.id] = inventory_section
    return created


@pytest.mark.django_db
class TestAssetScopeRoutes:
    def test_bases_list_hides_out_of_scope_assets(self, scoped, scope_setup):
        ids = [a["id"] for a in scoped.get("/asset/bases/").data]
        assert ids == [scope_setup.visible.id]

    def test_bases_count_hides_out_of_scope_assets(self, scoped, scope_setup):
        assert scoped.get("/asset/bases/?limit=10").data["count"] == 1

    def test_bases_detail_of_hidden_asset_is_404(self, scoped, scope_setup):
        response = scoped.get(f"/asset/bases/{scope_setup.hidden.id}/")
        assert response.status_code == 404

    def test_unscoped_user_sees_all_bases(
        self, make_scoped_user, client_for, scope_setup
    ):
        client = client_for(make_scoped_user("view_inventorybase", username="plain"))
        assert len(client.get("/asset/bases/").data) == 2

    def test_sections_follow_scope(self, scoped, scope_setup, sections):
        bases = [s["base"] for s in scoped.get("/asset/sections/").data]
        assert bases == [scope_setup.visible.id]

    def test_fields_follow_scope(self, scoped, scope_setup, sections):
        expected = [sections[scope_setup.visible.id].id]
        data = scoped.get("/asset/fields/").data
        assert [f["inventory_section"] for f in data] == expected

    def test_logs_follow_scope(self, scoped, scope_setup):
        Log.objects.create(asset=scope_setup.visible, comment="a")
        Log.objects.create(asset=scope_setup.hidden, comment="b")
        assets = [log["asset"] for log in scoped.get("/asset/logs/").data]
        assert assets == [scope_setup.visible.id]

    def test_results_follow_scope(self, scoped, scope_setup):
        Result.objects.create(asset=scope_setup.visible, name="pkg")
        Result.objects.create(asset=scope_setup.hidden, name="pkg")
        data = scoped.get("/deployment/results/").data
        assert [r["asset"] for r in data] == [scope_setup.visible.id]

    def test_bulk_delete_with_hidden_id_deletes_nothing(self, scoped, scope_setup):
        response = scoped.post(
            "/asset/bases/?delete=1",
            {"ids": [scope_setup.visible.id, scope_setup.hidden.id]},
            format="json",
        )
        assert response.status_code == 404
        assert response.data["ids"] == [scope_setup.hidden.id]
        assert InventoryBase.objects.count() == 2
