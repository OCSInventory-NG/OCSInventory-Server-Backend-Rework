import pytest
from notes.models import Note
from virtualcolumn.models import ColumnLayout


def bulk_delete(client, route, ids):
    return client.post(f"/{route}/?delete=1", {"ids": ids}, format="json")


@pytest.mark.django_db
class TestBulkDestroy:
    """POST ?delete=1 must refuse whatever a DELETE refuses"""

    def note(self, user, text="note"):
        return Note.objects.create(text=text, creator=user)

    def test_deletes_every_listed_object(self, api_client, admin_user):
        notes = [self.note(admin_user), self.note(admin_user)]

        response = bulk_delete(api_client, "notes", [note.id for note in notes])

        assert response.status_code == 204
        assert not Note.objects.exists()

    def test_the_delete_permission_is_required(self, admin_user, make_api_client):
        note = self.note(admin_user)
        client = make_api_client("view_note", "add_note")

        response = bulk_delete(client, "notes", [note.id])

        assert response.status_code == 403
        assert Note.objects.filter(id=note.id).exists()

    def test_an_unknown_id_deletes_nothing(self, api_client, admin_user):
        note = self.note(admin_user)

        response = bulk_delete(api_client, "notes", [note.id, 999999])

        assert response.status_code == 404
        assert response.data["ids"] == [999999]
        assert Note.objects.filter(id=note.id).exists()

    @pytest.mark.parametrize("ids", [None, [], "1", ["abc"], [[1]], {"a": 1}])
    def test_malformed_ids_are_refused(self, api_client, admin_user, ids):
        note = self.note(admin_user)

        response = bulk_delete(api_client, "notes", ids)

        assert response.status_code == 400
        assert Note.objects.filter(id=note.id).exists()

    def test_a_missing_ids_key_is_refused(self, api_client):
        response = api_client.post("/notes/?delete=1", {}, format="json")

        assert response.status_code == 400


@pytest.mark.django_db
class TestBulkDestroyOfRestrictedObjects:
    """The visibility and ownership rules hold through the bulk route"""

    def layout(self, owner, **kwargs):
        return ColumnLayout.objects.create(
            name="Support view", columns=["name"], user=owner, **kwargs
        )

    def other(self, make_api_client, django_user_model=None, group=None):
        client = make_api_client(
            "view_columnlayout",
            "add_columnlayout",
            "delete_columnlayout",
            username="other",
        )
        if group is not None:
            django_user_model.objects.get(username="other").groups.add(group)
        return client

    def test_the_owner_deletes_their_layouts(self, api_client, admin_user):
        layouts = [self.layout(admin_user), self.layout(admin_user)]

        response = bulk_delete(
            api_client, "column_layouts", [layout.id for layout in layouts]
        )

        assert response.status_code == 204
        assert not ColumnLayout.objects.exists()

    def test_a_private_layout_of_someone_else_is_not_found(
        self, admin_user, make_api_client
    ):
        layout = self.layout(admin_user)
        client = self.other(make_api_client)

        response = bulk_delete(client, "column_layouts", [layout.id])

        assert response.status_code == 404
        assert ColumnLayout.objects.filter(id=layout.id).exists()

    def test_a_visible_layout_of_someone_else_is_refused(
        self, admin_user, make_api_client
    ):
        layout = self.layout(admin_user, visibility="public")
        client = self.other(make_api_client)

        response = bulk_delete(client, "column_layouts", [layout.id])

        assert response.status_code == 403
        assert ColumnLayout.objects.filter(id=layout.id).exists()

    def test_the_group_modification_flag_does_not_open_deletion(
        self, admin_user, make_api_client, django_user_model
    ):
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")
        layout = self.layout(
            admin_user, visibility="private_group", allow_group_modification=True
        )
        layout.groups.add(group)
        client = self.other(make_api_client, django_user_model, group)

        response = bulk_delete(client, "column_layouts", [layout.id])

        assert response.status_code == 403
        assert ColumnLayout.objects.filter(id=layout.id).exists()

    def test_one_refused_id_spares_the_others(self, admin_user, make_api_client):
        """All or nothing, an own layout listed beside a foreign one stays"""
        foreign = self.layout(admin_user, visibility="public")
        client = self.other(make_api_client)
        own_id = client.post(
            "/column_layouts/", {"name": "Mine", "columns": ["name"]}, format="json"
        ).data["id"]

        response = bulk_delete(client, "column_layouts", [own_id, foreign.id])

        assert response.status_code == 403
        assert ColumnLayout.objects.filter(id__in=[own_id, foreign.id]).count() == 2
