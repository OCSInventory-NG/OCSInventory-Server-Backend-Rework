import pytest
from inventory.category.models import Category
from inventory.section.models import Section
from inventory.template.models import Template
from rest_framework.test import APIClient


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


@pytest.fixture
def section(template):
    return Section.objects.create(name="OS", target="os", template=template)


@pytest.mark.django_db
class TestCategoryList:
    def test_list_includes_created_category(self, api_client):
        Category.objects.create(name="Custom category", description="desc")

        response = api_client.get("/categories/")

        assert response.status_code == 200
        names = [category["name"] for category in response.data]
        assert "Custom category" in names

    def test_list_requires_authentication(self):
        response = APIClient().get("/categories/")

        assert response.status_code == 401


@pytest.mark.django_db
class TestCategoryCreate:
    def test_create_minimal_category(self, api_client):
        response = api_client.post(
            "/categories/",
            {"name": "Custom category", "description": "Network devices"},
            format="json",
        )

        assert response.status_code == 201
        category = Category.objects.get(name="Custom category")
        assert category.description == "Network devices"
        assert category.is_protected is False

    def test_create_with_inventory_sections(self, api_client, section):
        response = api_client.post(
            "/categories/",
            {
                "name": "Custom category",
                "description": "Network devices",
                "inventory_sections": [section.id],
            },
            format="json",
        )

        assert response.status_code == 201
        category = Category.objects.get(name="Custom category")
        assert list(category.inventory_sections.values_list("id", flat=True)) == [
            section.id
        ]

    def test_create_requires_add_permission(self, make_api_client):
        client = make_api_client("view_category")

        response = client.post(
            "/categories/",
            {"name": "Custom category", "description": "Network devices"},
            format="json",
        )

        assert response.status_code == 403
        assert not Category.objects.filter(name="Custom category").exists()


@pytest.mark.django_db
class TestCategoryUpdate:
    def test_partial_update_changes_only_given_fields(self, api_client):
        category = Category.objects.create(name="Custom category", description="Old desc")

        response = api_client.patch(
            f"/categories/{category.id}/",
            {"description": "New desc"},
            format="json",
        )

        assert response.status_code == 200
        category.refresh_from_db()
        assert category.name == "Custom category"
        assert category.description == "New desc"


@pytest.mark.django_db
class TestCategoryDelete:
    def test_delete_removes_category(self, api_client):
        category = Category.objects.create(name="Custom category", description="desc")

        response = api_client.delete(f"/categories/{category.id}/")

        assert response.status_code == 204
        assert not Category.objects.filter(id=category.id).exists()

    def test_delete_does_not_remove_linked_sections(self, api_client, section):
        category = Category.objects.create(name="Custom category", description="desc")
        category.inventory_sections.add(section)

        api_client.delete(f"/categories/{category.id}/")

        assert Section.objects.filter(id=section.id).exists()
