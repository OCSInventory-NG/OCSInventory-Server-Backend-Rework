import pytest
from django.contrib.auth.models import Group, Permission
from debug.resolver import resolve_calls
from mgmt.management.commands.migrate import Command as MigrateCommand


@pytest.mark.django_db
def test_debug_mode_permission_exists():
    permission = Permission.objects.get(
        content_type__app_label="debug", codename="view_debugmode"
    )
    assert permission.name == "Can view debug mode"


@pytest.mark.django_db
def test_default_groups_get_debug_mode_permission():
    MigrateCommand().assign_group_permissions()

    for group_name in ("super-admin", "admin", "user"):
        group = Group.objects.get(name=group_name)
        assert group.permissions.filter(
            content_type__app_label="debug", codename="view_debugmode"
        ).exists()


def resolve_one(method, path):
    return resolve_calls([{"method": method, "path": path}])


def codenames(entry):
    return [permission["codename"] for permission in entry["permissions"]]


@pytest.mark.django_db
def test_model_permission_list_call():
    result = resolve_one("GET", "asset/bases/?accountinfo=true")
    call = result["calls"][0]

    assert call["path"] == "asset/bases/"
    assert call["operation"] == "list"
    assert call["access"] == "permissions"
    assert codenames(call) == ["inventory_base.view_inventorybase"]
    assert call["permissions"][0]["name"] == "Can view inventory base"


@pytest.mark.django_db
def test_detail_call():
    call = resolve_one("DELETE", "asset/bases/12/")["calls"][0]

    assert call["operation"] == "destroy"
    assert codenames(call) == ["inventory_base.delete_inventorybase"]


@pytest.mark.django_db
def test_options_only_needs_authentication():
    call = resolve_one("OPTIONS", "asset/bases/")["calls"][0]

    assert call["operation"] == "metadata"
    assert call["access"] == "authenticated"
    assert call["permissions"] == []


@pytest.mark.django_db
def test_bulk_delete_needs_add_permission():
    call = resolve_one("POST", "asset/bases/?delete=true")["calls"][0]

    assert call["operation"] == "create"
    assert codenames(call) == ["inventory_base.add_inventorybase"]


@pytest.mark.django_db
def test_extra_action_call():
    call = resolve_one("POST", "templates/3/versions/1/rollback/")["calls"][0]

    assert call["operation"] == "rollback"
    assert codenames(call) == ["template.add_template"]


@pytest.mark.django_db
def test_is_authenticated_view():
    call = resolve_one("GET", "myaccount/")["calls"][0]

    assert call["access"] == "authenticated"


@pytest.mark.django_db
def test_method_excluded_by_http_method_names():
    call = resolve_one("POST", "myaccount/")["calls"][0]

    assert call["access"] == "error"
    assert call["detail"] == "method_not_allowed"


@pytest.mark.django_db
def test_method_not_bound_on_route():
    call = resolve_one("PUT", "asset/bases/")["calls"][0]

    assert call["access"] == "error"
    assert call["detail"] == "method_not_allowed"


@pytest.mark.django_db
def test_public_view():
    call = resolve_one("GET", "api-check/")["calls"][0]

    assert call["operation"] == "api_check"
    assert call["access"] == "public"


@pytest.mark.django_db
def test_plain_api_view():
    call = resolve_one("POST", "search/")["calls"][0]

    assert call["operation"] == "post"
    assert call["access"] == "public"


@pytest.mark.django_db
def test_unknown_endpoint():
    call = resolve_one("GET", "does-not-exist/")["calls"][0]

    assert call["access"] == "error"
    assert call["detail"] == "unknown_endpoint"


@pytest.mark.django_db
def test_non_api_view():
    call = resolve_one("GET", "api-auth/login/")["calls"][0]

    assert call["access"] == "error"
    assert call["detail"] == "not_api_endpoint"


RESOLVE_URL = "/debug/resolve/"


@pytest.mark.django_db
def test_resolve_endpoint_requires_debug_permission(make_api_client):
    client = make_api_client("view_inventorybase")

    response = client.post(RESOLVE_URL, {"calls": []}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_resolve_endpoint(make_api_client):
    client = make_api_client("view_debugmode")

    response = client.post(
        RESOLVE_URL,
        {"calls": [{"method": "GET", "path": "asset/bases/"}]},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["calls"][0]["operation"] == "list"


@pytest.mark.django_db
def test_resolve_endpoint_rejects_invalid_payload(make_api_client):
    client = make_api_client("view_debugmode")

    response = client.post(
        RESOLVE_URL, {"calls": [{"method": "FETCH", "path": ""}]}, format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_resolve_endpoint_describes_itself_as_custom(make_api_client):
    client = make_api_client("view_debugmode")

    response = client.post(
        RESOLVE_URL,
        {"calls": [{"method": "POST", "path": "debug/resolve/"}]},
        format="json",
    )

    assert response.data["calls"][0]["access"] == "custom"
    assert response.data["calls"][0]["detail"] == "HasDebugMode"
