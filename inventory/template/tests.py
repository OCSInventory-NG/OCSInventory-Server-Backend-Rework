import pytest
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template, TemplateVersion


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


@pytest.fixture
def section(template):
    return Section.objects.create(name="OS", target="os", template=template)


@pytest.fixture
def field(section):
    return Field.objects.create(name="Name", section=section, order=1)


@pytest.mark.django_db
class TestTemplateCreate:
    def test_create_protected_template_takes_initial_snapshot(self, api_client):
        response = api_client.post(
            "/templates/",
            {"name": "Custom", "os": "WIN", "is_protected": True, "sections": []},
            format="json",
        )

        assert response.status_code == 201
        template = Template.objects.get(name="Custom")
        versions = TemplateVersion.objects.filter(template=template)
        assert versions.count() == 1
        assert versions.first().label == "Initial version"

    def test_create_regular_template_takes_no_snapshot(self, api_client):
        response = api_client.post(
            "/templates/",
            {"name": "Custom", "os": "WIN", "is_protected": False, "sections": []},
            format="json",
        )

        assert response.status_code == 201
        template = Template.objects.get(name="Custom")
        assert TemplateVersion.objects.filter(template=template).count() == 0


@pytest.mark.django_db
class TestTemplateExport:
    def test_export_strips_ids_and_forces_unprotected(
        self, api_client, template, section, field
    ):
        template.is_protected = True
        template.save()

        response = api_client.get(f"/templates/{template.id}/export/")

        assert response.status_code == 200
        assert response.data["is_protected"] is False
        assert response.data["schema_version"] == 1
        assert "id" not in response.data
        section_data = response.data["sections"][0]
        assert "id" not in section_data
        assert section_data["fields"][0]["name"] == "Name"


@pytest.mark.django_db
class TestTemplateImportSections:
    def test_import_sections_appends_new_section_with_fields(
        self, api_client, template
    ):
        response = api_client.post(
            f"/templates/{template.id}/import-sections/",
            {
                "sections": [
                    {
                        "id": 9999,
                        "name": "Imported section",
                        "retrieval_method": "FILE",
                        "retrieval_output": "JSON",
                        "target": "target",
                        "fields": [
                            {"name": "Imported field", "order": 1},
                        ],
                    }
                ]
            },
            format="json",
        )

        assert response.status_code == 201
        imported_section = template.sections.get(name="Imported section")
        assert imported_section.id != 9999
        assert imported_section.fields.get().name == "Imported field"

    def test_import_sections_rejects_empty_payload(self, api_client, template):
        response = api_client.post(
            f"/templates/{template.id}/import-sections/",
            {"sections": []},
            format="json",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestTemplateVersions:
    def test_post_creates_a_new_version_with_label(self, api_client, template):
        response = api_client.post(
            f"/templates/{template.id}/versions/",
            {"label": "Before big change"},
            format="json",
        )

        assert response.status_code == 201
        assert response.data["label"] == "Before big change"
        assert response.data["revision"] == 1

    def test_revision_numbers_increment_and_are_never_reused(
        self, api_client, template
    ):
        api_client.post(f"/templates/{template.id}/versions/", {}, format="json")
        second = api_client.post(
            f"/templates/{template.id}/versions/", {}, format="json"
        )
        assert second.data["revision"] == 2

        TemplateVersion.objects.get(template=template, revision=1).delete()

        third = api_client.post(
            f"/templates/{template.id}/versions/", {}, format="json"
        )
        assert third.data["revision"] == 3

    def test_get_lists_version_history_without_full_snapshot(
        self, api_client, template
    ):
        TemplateVersion.create_snapshot(template, label="v1")

        response = api_client.get(f"/templates/{template.id}/versions/")

        assert response.status_code == 200
        assert len(response.data) == 1
        assert "snapshot" not in response.data[0]


@pytest.mark.django_db
class TestTemplateVersionDetail:
    def test_get_returns_full_snapshot(self, api_client, template, section, field):
        version = TemplateVersion.create_snapshot(template, label="v1")

        response = api_client.get(f"/templates/{template.id}/versions/{version.id}/")

        assert response.status_code == 200
        assert response.data["snapshot"]["sections"][0]["fields"][0]["name"] == "Name"

    def test_delete_removes_non_initial_version(self, api_client, template):
        version = TemplateVersion.create_snapshot(template, label="v1")

        response = api_client.delete(f"/templates/{template.id}/versions/{version.id}/")

        assert response.status_code == 204
        assert not TemplateVersion.objects.filter(id=version.id).exists()

    def test_delete_rejects_initial_version_of_protected_template(self, api_client):
        template = Template.objects.create(
            name="Protected", os="WIN", is_protected=True
        )
        version = TemplateVersion.create_snapshot(template, label="Initial version")

        response = api_client.delete(f"/templates/{template.id}/versions/{version.id}/")

        assert response.status_code == 400
        assert TemplateVersion.objects.filter(id=version.id).exists()


@pytest.mark.django_db
class TestTemplateRollback:
    def test_rollback_restores_template_attrs(self, api_client, template):
        version = TemplateVersion.create_snapshot(template, label="v1")
        template.name = "Renamed"
        template.save()

        response = api_client.post(
            f"/templates/{template.id}/versions/{version.id}/rollback/"
        )

        assert response.status_code == 200
        template.refresh_from_db()
        assert template.name == "Windows"

    def test_rollback_restores_deleted_section_by_id(
        self, api_client, template, section, field
    ):
        version = TemplateVersion.create_snapshot(template, label="v1")
        section.delete()

        response = api_client.post(
            f"/templates/{template.id}/versions/{version.id}/rollback/"
        )

        assert response.status_code == 200
        assert template.sections.filter(name="OS").exists()
        restored_section = template.sections.get(name="OS")
        assert restored_section.fields.filter(name="Name").exists()

    def test_rollback_removes_section_created_after_snapshot(
        self, api_client, template, section
    ):
        version = TemplateVersion.create_snapshot(template, label="v1")
        Section.objects.create(name="New section", target="new", template=template)

        response = api_client.post(
            f"/templates/{template.id}/versions/{version.id}/rollback/"
        )

        assert response.status_code == 200
        assert not template.sections.filter(name="New section").exists()
        assert template.sections.filter(name="OS").exists()

    def test_rollback_updates_modified_section_in_place_preserving_id(
        self, api_client, template, section
    ):
        version = TemplateVersion.create_snapshot(template, label="v1")
        section_id = section.id
        section.name = "Renamed section"
        section.save()

        response = api_client.post(
            f"/templates/{template.id}/versions/{version.id}/rollback/"
        )

        assert response.status_code == 200
        section.refresh_from_db()
        assert section.id == section_id
        assert section.name == "OS"
