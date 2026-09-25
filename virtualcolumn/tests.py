import pytest
from asset.inventory_base.models import InventoryBase
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from django.db import connection
from django.test.utils import CaptureQueriesContext
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.template.models import Template
from virtualcolumn.models import VirtualCol


@pytest.fixture
def park(db):
    """
    Two templates naming the same information differently, plus an asset on a
    third template that does not carry it at all.
    """
    park = {}

    for key, template_name, section_name, field_name in (
        ("win", "Windows", "BIOS", "MANUFACTURER"),
        ("deb", "Debian", "OSINFO", "BIOSMANUF"),
        ("mac", "MacOS", "HARDWARE", "CPU"),
    ):
        template = Template.objects.create(name=template_name)
        section = Section.objects.create(name=section_name, template=template)
        field = Field.objects.create(name=field_name, section=section)
        park[key] = {"template": template, "section": section, "field": field}

    return park


def make_asset(park, key, name, value):
    entry = park[key]
    asset = InventoryBase.objects.create(
        name=name, osname="os", uuid=name, template=entry["template"]
    )
    inventory_section = InventorySection.objects.create(
        base=asset, template_section=entry["section"]
    )
    InventoryField.objects.create(
        inventory_section=inventory_section,
        template_field=entry["field"],
        value=value,
    )
    return asset


def rows(response):
    """The listing is only paginated when the request asks for a limit"""
    data = response.data
    return data["results"] if isinstance(data, dict) else data


@pytest.mark.django_db
class TestVirtualCol:
    def build_column(self, park, admin_user, keys):
        return VirtualCol.objects.create(
            name="BIOS NAME",
            target="asset",
            mapping={
                str(park[key]["template"].id): park[key]["field"].id for key in keys
            },
            user=admin_user,
            visibility="public",
        )

    def test_each_asset_reads_the_field_of_its_own_template(
        self, api_client, admin_user, park
    ):
        """One column, two templates naming the field differently."""
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        make_asset(park, "deb", "PC-DEB", "Lenovo")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert response.status_code == 200
        values = {
            row["name"]: row["virtual_cols"][column.key] for row in rows(response)
        }
        assert values == {"PC-WIN": "Dell Inc.", "PC-DEB": "Lenovo"}

    def test_template_absent_from_the_mapping_yields_an_empty_cell(
        self, api_client, admin_user, park
    ):
        """The column stays present, the asset simply has no value for it."""
        make_asset(park, "mac", "PC-MAC", "Apple M1")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert rows(response)[0]["virtual_cols"] == {column.key: None}

    def test_repeated_section_keeps_the_first_value_and_counts_the_others(
        self, api_client, admin_user, park
    ):
        asset = make_asset(park, "win", "PC-WIN", "first")
        for value in ("second", "third"):
            extra = InventorySection.objects.create(
                base=asset, template_section=park["win"]["section"]
            )
            InventoryField.objects.create(
                inventory_section=extra,
                template_field=park["win"]["field"],
                value=value,
            )
        column = self.build_column(park, admin_user, ["win"])

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert rows(response)[0]["virtual_cols"][column.key] == "first (+2)"

    def test_columns_are_omitted_when_not_requested(self, api_client, admin_user, park):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        self.build_column(park, admin_user, ["win"])

        response = api_client.get("/asset/bases/")

        assert "virtual_cols" not in rows(response)[0]

    def test_a_column_costs_one_query_whatever_the_page_size(
        self, api_client, admin_user, park
    ):
        """The values are fetched for the whole page at once, never per asset"""
        for index in range(5):
            make_asset(park, "win", f"PC-{index}", f"value-{index}")
        column = self.build_column(park, admin_user, ["win", "deb"])

        with CaptureQueriesContext(connection) as captured:
            api_client.get("/asset/bases/", {"virtual_cols": column.id})

        inventory_queries = [
            query
            for query in captured.captured_queries
            if "inventory_field_inventoryfield" in query["sql"]
        ]
        assert len(inventory_queries) == 1

    def test_a_private_column_is_not_resolved_for_another_user(
        self, make_api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = self.build_column(park, admin_user, ["win"])
        column.visibility = "private_personal"
        column.save()

        client = make_api_client("view_inventorybase")
        response = client.get("/asset/bases/", {"virtual_cols": column.id})

        assert response.status_code == 200
        assert "virtual_cols" not in rows(response)[0]


@pytest.mark.django_db
class TestVirtualColApi:
    def test_creating_a_column_does_not_require_an_owner_in_the_payload(
        self, api_client, admin_user, park
    ):
        """The creator owns the column, the client never states it"""
        response = api_client.post(
            "/virtual_cols/",
            {
                "name": "BIOS NAME",
                "target": "asset",
                "visibility": "public",
                "mapping": {str(park["win"]["template"].id): park["win"]["field"].id},
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        column = VirtualCol.objects.get(name="BIOS NAME")
        assert column.user == admin_user

    def test_the_payload_cannot_hand_the_column_to_someone_else(
        self, api_client, admin_user, django_user_model, park
    ):
        other = django_user_model.objects.create_user(username="someone-else")

        response = api_client.post(
            "/virtual_cols/",
            {
                "name": "BIOS NAME",
                "target": "asset",
                "mapping": {str(park["win"]["template"].id): park["win"]["field"].id},
                "user": other.id,
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert VirtualCol.objects.get(name="BIOS NAME").user == admin_user

    def test_mapping_entries_are_normalised(self, api_client, park):
        response = api_client.post(
            "/virtual_cols/",
            {
                "name": "BIOS NAME",
                "target": "asset",
                "mapping": {
                    str(park["win"]["template"].id): str(park["win"]["field"].id),
                    str(park["deb"]["template"].id): "",
                },
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert VirtualCol.objects.get(name="BIOS NAME").mapping == {
            str(park["win"]["template"].id): park["win"]["field"].id
        }


@pytest.mark.django_db
class TestVirtualColSearch:
    def build_column(self, park, admin_user, keys):
        return VirtualCol.objects.create(
            name="BIOS NAME",
            target="asset",
            mapping={
                str(park[key]["template"].id): park[key]["field"].id for key in keys
            },
            user=admin_user,
            visibility="public",
        )

    def test_the_quick_search_reaches_a_displayed_virtual_column(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        make_asset(park, "deb", "PC-DEB", "Lenovo")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "search": "lenovo"}
        )

        assert [row["name"] for row in rows(response)] == ["PC-DEB"]

    def test_the_search_still_matches_the_asset_own_fields(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        make_asset(park, "deb", "PC-DEB", "Lenovo")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "search": "PC-WIN"}
        )

        assert [row["name"] for row in rows(response)] == ["PC-WIN"]

    def test_an_asset_matching_on_both_sides_appears_once(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "Lenovo-01", "Lenovo")
        column = self.build_column(park, admin_user, ["win"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "search": "lenovo"}
        )

        assert len(rows(response)) == 1

    def test_a_column_that_is_not_displayed_is_not_searched(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        self.build_column(park, admin_user, ["win"])

        response = api_client.get("/asset/bases/", {"search": "dell"})

        assert rows(response) == []


@pytest.mark.django_db
class TestVirtualColOrdering:
    def build_column(self, park, admin_user, keys):
        return VirtualCol.objects.create(
            name="BIOS NAME",
            target="asset",
            mapping={
                str(park[key]["template"].id): park[key]["field"].id for key in keys
            },
            user=admin_user,
            visibility="public",
        )

    def test_sorting_ascending_uses_the_value_of_each_own_template(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Zebra")
        make_asset(park, "deb", "PC-DEB", "Acme")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "ordering": column.key}
        )

        assert [row["name"] for row in rows(response)] == ["PC-DEB", "PC-WIN"]

    def test_sorting_descending(self, api_client, admin_user, park):
        make_asset(park, "win", "PC-WIN", "Zebra")
        make_asset(park, "deb", "PC-DEB", "Acme")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "ordering": "-" + column.key}
        )

        assert [row["name"] for row in rows(response)] == ["PC-WIN", "PC-DEB"]

    def test_assets_without_a_value_are_last_both_ways(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Zebra")
        make_asset(park, "deb", "PC-DEB", "Acme")
        make_asset(park, "mac", "PC-MAC", "not mapped")
        column = self.build_column(park, admin_user, ["win", "deb"])

        for ordering in (column.key, "-" + column.key):
            response = api_client.get(
                "/asset/bases/", {"virtual_cols": column.id, "ordering": ordering}
            )
            assert [row["name"] for row in rows(response)][-1] == "PC-MAC"

    def test_the_sort_key_is_the_value_the_cell_shows(
        self, api_client, admin_user, park
    ):
        """A repeated section shows its first value, so it sorts on that one"""
        asset = make_asset(park, "win", "PC-WIN", "Alpha")
        extra = InventorySection.objects.create(
            base=asset, template_section=park["win"]["section"]
        )
        InventoryField.objects.create(
            inventory_section=extra, template_field=park["win"]["field"], value="Zulu"
        )
        make_asset(park, "deb", "PC-DEB", "Bravo")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "ordering": column.key}
        )

        listed = rows(response)
        assert listed[0]["virtual_cols"][column.key] == "Alpha (+1)"
        assert [row["name"] for row in listed] == ["PC-WIN", "PC-DEB"]

    def test_ordering_on_a_native_column_is_untouched(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Zebra")
        make_asset(park, "deb", "PC-DEB", "Acme")
        column = self.build_column(park, admin_user, ["win", "deb"])

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "ordering": "-name"}
        )

        assert [row["name"] for row in rows(response)] == ["PC-WIN", "PC-DEB"]


@pytest.mark.django_db
class TestVirtualColVisibility:
    def column_for(self, park, owner, **kwargs):
        return VirtualCol.objects.create(
            name="CPU SPEED",
            target="asset",
            mapping={str(park["win"]["template"].id): park["win"]["field"].id},
            user=owner,
            **kwargs,
        )

    def test_a_group_column_reaches_the_members_of_that_group(
        self, api_client, admin_user, make_api_client, park, django_user_model
    ):
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")
        admin_user.groups.add(group)
        column = self.column_for(park, admin_user, visibility="private_group")
        column.groups.add(group)

        member = make_api_client("view_virtualcol", username="member")
        django_user_model.objects.get(username="member").groups.add(group)

        listed = member.get("/virtual_cols/").data
        assert [col["name"] for col in listed] == ["CPU SPEED"]

    def test_a_group_column_without_a_group_reaches_nobody_else(
        self, admin_user, make_api_client, park
    ):
        """What the form used to produce : the column stayed invisible"""
        self.column_for(park, admin_user, visibility="private_group")

        listed = (
            make_api_client("view_virtualcol", username="outsider")
            .get("/virtual_cols/")
            .data
        )

        assert listed == []

    def test_groups_sent_on_create_are_kept(self, api_client, admin_user, park):
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")

        response = api_client.post(
            "/virtual_cols/",
            {
                "name": "CPU SPEED",
                "target": "asset",
                "visibility": "private_group",
                "groups": [group.id],
                "mapping": {str(park["win"]["template"].id): park["win"]["field"].id},
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert list(
            VirtualCol.objects.get(name="CPU SPEED").groups.values_list(
                "name", flat=True
            )
        ) == ["support"]


@pytest.mark.django_db
class TestVirtualColEdgeCases:
    def column_for(self, park, owner, keys=("win",), **kwargs):
        return VirtualCol.objects.create(
            name=kwargs.pop("name", "BIOS NAME"),
            target="asset",
            mapping={
                str(park[key]["template"].id): park[key]["field"].id for key in keys
            },
            user=owner,
            visibility=kwargs.pop("visibility", "public"),
            **kwargs,
        )

    @pytest.mark.parametrize("value", ["999999", "abc", "", "1,,2", "-1", "1;2"])
    def test_a_junk_parameter_falls_back_to_the_plain_listing(
        self, api_client, park, value
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")

        response = api_client.get("/asset/bases/", {"virtual_cols": value})

        assert response.status_code == 200
        assert [row["name"] for row in rows(response)] == ["PC-WIN"]

    def test_a_column_whose_field_was_deleted_stays_empty_without_failing(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = self.column_for(park, admin_user)
        park["win"]["field"].delete()

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert response.status_code == 200
        assert rows(response)[0]["virtual_cols"] == {column.key: None}

    def test_a_column_whose_template_was_deleted_stays_empty_without_failing(
        self, api_client, admin_user, park
    ):
        make_asset(park, "deb", "PC-DEB", "Lenovo")
        column = self.column_for(park, admin_user, keys=("win", "deb"))
        park["win"]["template"].delete()

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert response.status_code == 200
        assert rows(response)[0]["virtual_cols"][column.key] == "Lenovo"

    def test_a_column_with_an_empty_mapping_is_shown_but_never_filled(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = VirtualCol.objects.create(
            name="EMPTY",
            target="asset",
            mapping={},
            user=admin_user,
            visibility="public",
        )

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert rows(response)[0]["virtual_cols"] == {column.key: None}

    def test_ordering_on_an_unknown_name_falls_back_to_the_default(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = self.column_for(park, admin_user)

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": column.id, "ordering": "NOT A COLUMN"}
        )

        assert response.status_code == 200
        assert len(rows(response)) == 1

    def test_search_and_sort_on_the_column_at_once(self, api_client, admin_user, park):
        make_asset(park, "win", "PC-A", "Dell Inc.")
        make_asset(park, "win", "PC-B", "Dell Inc.")
        make_asset(park, "win", "PC-C", "Lenovo")
        column = self.column_for(park, admin_user)

        response = api_client.get(
            "/asset/bases/",
            {
                "virtual_cols": column.id,
                "search": "dell",
                "ordering": "-" + column.key,
            },
        )

        assert sorted(row["name"] for row in rows(response)) == ["PC-A", "PC-B"]

    def test_pagination_keeps_the_count_and_the_columns(
        self, api_client, admin_user, park
    ):
        for index in range(7):
            make_asset(park, "win", f"PC-{index}", f"value-{index}")
        column = self.column_for(park, admin_user)

        response = api_client.get(
            "/asset/bases/",
            {"virtual_cols": column.id, "limit": 3, "ordering": column.key},
        )

        assert response.data["count"] == 7
        assert len(response.data["results"]) == 3
        assert response.data["results"][0]["virtual_cols"][column.key] == "value-0"

    def test_retrieving_a_single_asset_is_untouched(self, api_client, admin_user, park):
        asset = make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = self.column_for(park, admin_user)

        response = api_client.get(
            f"/asset/bases/{asset.id}/", {"virtual_cols": column.id}
        )

        assert response.status_code == 200
        assert response.data["name"] == "PC-WIN"

    def test_two_users_may_each_keep_a_private_column_of_the_same_name(
        self, make_api_client, admin_user, park
    ):
        self.column_for(park, admin_user, visibility="private_personal")

        client = make_api_client("add_virtualcol", username="other")
        response = client.post(
            "/virtual_cols/",
            {"name": "BIOS NAME", "target": "asset", "mapping": {}},
            format="json",
        )

        assert response.status_code == 201

    def test_columns_sharing_a_name_do_not_overwrite_each_other(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        first = self.column_for(park, admin_user)
        second = self.column_for(park, admin_user, keys=("deb",))

        response = api_client.get(
            "/asset/bases/", {"virtual_cols": f"{first.id},{second.id}"}
        )

        assert rows(response)[0]["virtual_cols"] == {
            first.key: "Dell Inc.",
            second.key: None,
        }

    def test_a_column_named_like_a_native_field_leaves_it_alone(
        self, api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = self.column_for(park, admin_user, name="name")

        response = api_client.get("/asset/bases/", {"virtual_cols": column.id})

        assert rows(response)[0]["name"] == "PC-WIN"
        assert rows(response)[0]["virtual_cols"] == {column.key: "Dell Inc."}

    def test_asking_for_a_column_of_somebody_else_resolves_nothing(
        self, make_api_client, admin_user, park
    ):
        make_asset(park, "win", "PC-WIN", "Dell Inc.")
        column = self.column_for(park, admin_user, visibility="private_personal")

        client = make_api_client("view_inventorybase", username="nosy")
        response = client.get("/asset/bases/", {"virtual_cols": column.id})

        assert response.status_code == 200
        assert "virtual_cols" not in rows(response)[0]


@pytest.mark.django_db
class TestVirtualColGroupModification:
    def shared_column(self, park, owner, group, allow):
        column = VirtualCol.objects.create(
            name="CPU SPEED",
            target="asset",
            mapping={str(park["win"]["template"].id): park["win"]["field"].id},
            user=owner,
            visibility="private_group",
            allow_group_modification=allow,
        )
        column.groups.add(group)
        return column

    def member_client(self, make_api_client, django_user_model, group):
        client = make_api_client(
            "view_virtualcol",
            "change_virtualcol",
            "delete_virtualcol",
            username="member",
        )
        django_user_model.objects.get(username="member").groups.add(group)
        return client

    def test_a_member_may_edit_when_the_author_allows_it(
        self, admin_user, make_api_client, django_user_model, park
    ):
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")
        column = self.shared_column(park, admin_user, group, allow=True)
        client = self.member_client(make_api_client, django_user_model, group)

        response = client.patch(
            f"/virtual_cols/{column.id}/", {"name": "CPU FREQ"}, format="json"
        )

        assert response.status_code == 200, response.data
        column.refresh_from_db()
        assert column.name == "CPU FREQ"

    def test_a_member_may_not_edit_otherwise(
        self, admin_user, make_api_client, django_user_model, park
    ):
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")
        column = self.shared_column(park, admin_user, group, allow=False)
        client = self.member_client(make_api_client, django_user_model, group)

        response = client.patch(
            f"/virtual_cols/{column.id}/", {"name": "CPU FREQ"}, format="json"
        )

        assert response.status_code == 403

    def test_deleting_stays_reserved_to_the_author(
        self, admin_user, make_api_client, django_user_model, park
    ):
        """RestrictVisibility never opens deletion, whatever the flag says"""
        from django.contrib.auth.models import Group

        group = Group.objects.create(name="support")
        column = self.shared_column(park, admin_user, group, allow=True)
        client = self.member_client(make_api_client, django_user_model, group)

        assert client.delete(f"/virtual_cols/{column.id}/").status_code == 403
