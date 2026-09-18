import pytest
from freezegun import freeze_time
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


@pytest.mark.django_db
class TestSectionIsActive:
    def test_defaults_to_active(self, template):
        section = Section.objects.create(name="OS", target="os", template=template)

        assert section.is_active is True

    def test_can_be_created_inactive(self, template):
        section = Section.objects.create(
            name="OS", target="os", template=template, is_active=False
        )

        assert section.is_active is False

    def test_list_can_be_filtered_by_is_active(self, api_client, template):
        Section.objects.create(
            name="Active", target="os", template=template, is_active=True
        )
        Section.objects.create(
            name="Inactive", target="os", template=template, is_active=False
        )

        response = api_client.get("/sections/?is_active=false")

        assert response.status_code == 200
        names = [section["name"] for section in response.data]
        assert names == ["Inactive"]

    def test_update_can_toggle_is_active(self, api_client, template):
        section = Section.objects.create(name="OS", target="os", template=template)

        response = api_client.patch(
            f"/sections/{section.id}/", {"is_active": False}, format="json"
        )

        assert response.status_code == 200
        section.refresh_from_db()
        assert section.is_active is False


@pytest.mark.django_db
class TestSectionModelSignals:
    def test_saving_section_bumps_template_last_update(self, template):
        with freeze_time("2020-01-01 00:00:00"):
            template.save()
        initial_last_update = template.last_update

        with freeze_time("2020-01-02 00:00:00"):
            Section.objects.create(name="OS", target="os", template=template)

        template.refresh_from_db()
        assert template.last_update > initial_last_update

    def test_deleting_section_bumps_template_last_update(self, template):
        section = Section.objects.create(name="OS", target="os", template=template)

        with freeze_time("2020-01-01 00:00:00"):
            template.save()
        initial_last_update = template.last_update

        with freeze_time("2020-01-02 00:00:00"):
            section.delete()

        template.refresh_from_db()
        assert template.last_update > initial_last_update


@pytest.mark.django_db
class TestSectionList:
    def test_list_includes_created_section(self, api_client, template):
        Section.objects.create(name="OS", target="os", template=template)

        response = api_client.get("/sections/")

        assert response.status_code == 200
        names = [section["name"] for section in response.data]
        assert "OS" in names

    def test_list_requires_authentication(self):
        from rest_framework.test import APIClient

        response = APIClient().get("/sections/")

        assert response.status_code == 401


@pytest.mark.django_db
class TestSectionCreate:
    def test_create_minimal_section(self, api_client, template):
        response = api_client.post(
            "/sections/",
            {
                "name": "OS",
                "target": "os",
                "template": template.id,
                "retrieval_method": "FILE",
                "retrieval_output": "JSON",
                "fields": [],
            },
            format="json",
        )

        assert response.status_code == 201
        section = Section.objects.get(name="OS")
        assert section.template_id == template.id

    def test_create_with_nested_fields(self, api_client, template):
        response = api_client.post(
            "/sections/",
            {
                "name": "OS",
                "target": "os",
                "template": template.id,
                "retrieval_method": "FILE",
                "retrieval_output": "JSON",
                "fields": [
                    {"name": "Name", "order": 1},
                    {"name": "Version", "order": 2},
                ],
            },
            format="json",
        )

        assert response.status_code == 201
        section = Section.objects.get(name="OS")
        assert section.fields.count() == 2
        assert set(section.fields.values_list("name", flat=True)) == {
            "Name",
            "Version",
        }

    def test_create_requires_add_permission(self, make_api_client, template):
        client = make_api_client("view_section")

        response = client.post(
            "/sections/",
            {"name": "OS", "target": "os", "template": template.id},
            format="json",
        )

        assert response.status_code == 403
        assert not Section.objects.filter(name="OS").exists()


@pytest.mark.django_db
class TestSectionDelete:
    def test_delete_cascades_to_fields(self, api_client, template):
        section = Section.objects.create(name="OS", target="os", template=template)
        Field.objects.create(name="Name", section=section, order=1)

        response = api_client.delete(f"/sections/{section.id}/")

        assert response.status_code == 204
        assert Field.objects.filter(section_id=section.id).count() == 0
