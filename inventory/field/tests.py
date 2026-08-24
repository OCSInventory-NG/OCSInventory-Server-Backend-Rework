import pytest
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template


@pytest.fixture
def template(db):
    return Template.objects.create(name="Windows", os="WIN")


@pytest.fixture
def section(template):
    return Section.objects.create(name="OS", target="os", template=template)


@pytest.mark.django_db
class TestFieldOrderOnDelete:
    def test_deleting_a_field_decrements_order_of_later_siblings(self, section):
        first = Field.objects.create(name="First", section=section, order=1)
        second = Field.objects.create(name="Second", section=section, order=2)
        third = Field.objects.create(name="Third", section=section, order=3)

        first.delete()

        second.refresh_from_db()
        third.refresh_from_db()
        assert second.order == 1
        assert third.order == 2

    def test_deleting_a_field_does_not_affect_other_sections(self, section, template):
        other_section = Section.objects.create(
            name="Network", target="net", template=template
        )
        field_to_delete = Field.objects.create(name="First", section=section, order=1)
        other_field = Field.objects.create(name="Other", section=other_section, order=1)

        field_to_delete.delete()

        other_field.refresh_from_db()
        assert other_field.order == 1

    def test_deleting_section_does_not_raise_on_cascading_field_delete(self, section):
        section_id = section.id
        Field.objects.create(name="First", section=section, order=1)
        Field.objects.create(name="Second", section=section, order=2)

        # cascading delete triggers Field's post_delete for both fields;
        # the "origin is Section" guard must prevent DoesNotExist errors
        section.delete()

        assert Field.objects.filter(section_id=section_id).count() == 0


@pytest.mark.django_db
class TestFieldModelSignals:
    def test_saving_field_bumps_template_last_update(self, section, template):
        from freezegun import freeze_time

        with freeze_time("2020-01-01 00:00:00"):
            template.save()
        initial_last_update = template.last_update

        with freeze_time("2020-01-02 00:00:00"):
            Field.objects.create(name="Name", section=section, order=1)

        template.refresh_from_db()
        assert template.last_update > initial_last_update


@pytest.mark.django_db
class TestFieldCreateViaApi:
    def test_create_assigns_next_available_order(self, api_client, section):
        Field.objects.create(name="Existing", section=section, order=1)

        response = api_client.post(
            "/fields/",
            {"name": "New field", "section": section.id},
            format="json",
        )

        assert response.status_code == 201
        created = Field.objects.get(name="New field")
        assert created.order == 2

    def test_create_requires_add_permission(self, make_api_client, section):
        client = make_api_client("view_field")

        response = client.post(
            "/fields/",
            {"name": "New field", "section": section.id},
            format="json",
        )

        assert response.status_code == 403
        assert not Field.objects.filter(name="New field").exists()


@pytest.mark.django_db
class TestFieldUpdateOrder:
    def test_moving_field_to_lower_order_shifts_others_up(self, api_client, section):
        first = Field.objects.create(name="First", section=section, order=1)
        second = Field.objects.create(name="Second", section=section, order=2)
        third = Field.objects.create(name="Third", section=section, order=3)

        response = api_client.put(
            f"/fields/{third.id}/",
            {"name": "Third", "section": section.id, "order": 1},
            format="json",
        )

        assert response.status_code == 200
        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        assert third.order == 1
        assert first.order == 2
        assert second.order == 3

    def test_moving_field_to_higher_order_shifts_others_down(self, api_client, section):
        first = Field.objects.create(name="First", section=section, order=1)
        second = Field.objects.create(name="Second", section=section, order=2)
        third = Field.objects.create(name="Third", section=section, order=3)

        response = api_client.put(
            f"/fields/{first.id}/",
            {"name": "First", "section": section.id, "order": 3},
            format="json",
        )

        assert response.status_code == 200
        first.refresh_from_db()
        second.refresh_from_db()
        third.refresh_from_db()
        assert first.order == 3
        assert second.order == 1
        assert third.order == 2


@pytest.mark.django_db
class TestFieldFilterBySection:
    def test_filter_by_section_id_returns_only_matching_fields(
        self, api_client, section, template
    ):
        other_section = Section.objects.create(
            name="Network", target="net", template=template
        )
        Field.objects.create(name="OS field", section=section, order=1)
        Field.objects.create(name="Net field", section=other_section, order=1)

        response = api_client.get(f"/fields/?section={section.id}")

        assert response.status_code == 200
        names = [field["name"] for field in response.data]
        assert names == ["OS field"]

    def test_filter_by_stale_section_id_returns_empty_list_not_400(self, api_client):
        response = api_client.get("/fields/?section=999999")

        assert response.status_code == 200
        assert response.data == []
