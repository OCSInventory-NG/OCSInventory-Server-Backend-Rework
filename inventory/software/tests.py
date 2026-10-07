import pytest
from asset.inventory_base.models import InventoryBase
from asset.inventory_field.models import InventoryField
from asset.inventory_section.models import InventorySection
from inventory.field.models import Field
from inventory.section.models import Section
from inventory.software.models import (
    AssetPlatform,
    DistroRelease,
    SoftwareDictionary,
    SoftwareMapping,
)
from inventory.software.platform import resolve
from inventory.software.services import SoftwareDictionaryService
from inventory.template.models import Template


@pytest.fixture
def template(db):
    return Template.objects.create(name="Debian", os="DEB")


@pytest.fixture
def section(template):
    return Section.objects.create(
        name="SOFTWARES", target="softwares", template=template
    )


@pytest.fixture
def software_fields(section):
    return {
        "name": Field.objects.create(name="Name", section=section, order=1),
        "publisher": Field.objects.create(name="Publisher", section=section, order=2),
        "version": Field.objects.create(name="Version", section=section, order=3),
    }


@pytest.fixture
def mapping(template, section, software_fields):
    return SoftwareMapping.objects.create(
        template=template,
        section=section,
        name=software_fields["name"],
        publisher=software_fields["publisher"],
        version=software_fields["version"],
    )


@pytest.fixture
def asset(template):
    return InventoryBase.objects.create(
        name="asset-1",
        description="desc",
        serial="SER-1",
        osname="Linux",
        osversion="1",
        uuid="uuid-asset-1",
        domain="example",
        agent="agent",
        template=template,
        # avoids triggering the (unrelated) automation rule engine on save
        is_template_forced=True,
    )


def add_software_entry(asset, section, fields, *, name, publisher, version):
    inventory_section = InventorySection.objects.create(
        base=asset, template_section=section
    )
    InventoryField.objects.create(
        inventory_section=inventory_section,
        template_field=fields["name"],
        value=name,
    )
    InventoryField.objects.create(
        inventory_section=inventory_section,
        template_field=fields["publisher"],
        value=publisher,
    )
    InventoryField.objects.create(
        inventory_section=inventory_section,
        template_field=fields["version"],
        value=version,
    )
    return inventory_section


@pytest.mark.django_db
class TestSoftwareDictionaryServiceRefreshAsset:
    def test_refresh_asset_creates_entry_from_mapped_fields(
        self, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )

        SoftwareDictionaryService.refresh_asset(asset)

        entry = SoftwareDictionary.objects.get()
        assert entry.name == "apache2"
        assert entry.publisher == "Debian"
        assert entry.version == "2.4"
        assert entry.installation_number == 1
        assert asset in entry.assets.all()

    def test_refresh_asset_skips_entries_without_a_name(
        self, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset, section, software_fields, name="", publisher="Debian", version="2.4"
        )

        SoftwareDictionaryService.refresh_asset(asset)

        assert SoftwareDictionary.objects.count() == 0

    def test_refresh_asset_removes_stale_entries_no_longer_present(
        self, asset, section, software_fields, mapping
    ):
        inventory_section = add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        SoftwareDictionaryService.refresh_asset(asset)
        assert SoftwareDictionary.objects.count() == 1

        # software no longer present on next inventory
        inventory_section.delete()

        SoftwareDictionaryService.refresh_asset(asset)

        assert SoftwareDictionary.objects.count() == 0

    def test_refresh_asset_shares_entry_across_multiple_assets(
        self, asset, section, software_fields, mapping, template
    ):
        other_asset = InventoryBase.objects.create(
            name="asset-2",
            description="desc",
            serial="SER-2",
            osname="Linux",
            osversion="1",
            uuid="uuid-asset-2",
            domain="example",
            agent="agent",
            template=template,
            is_template_forced=True,
        )
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        add_software_entry(
            other_asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )

        SoftwareDictionaryService.refresh_asset(asset)
        SoftwareDictionaryService.refresh_asset(other_asset)

        assert SoftwareDictionary.objects.count() == 1
        entry = SoftwareDictionary.objects.get()
        assert entry.installation_number == 2
        assert set(entry.assets.all()) == {asset, other_asset}

    def test_refresh_asset_without_template_is_a_noop(self, template):
        asset = InventoryBase.objects.create(
            name="asset-3",
            description="desc",
            serial="SER-3",
            osname="Linux",
            osversion="1",
            uuid="uuid-asset-3",
            domain="example",
            agent="agent",
            template=None,
            is_template_forced=True,
        )

        SoftwareDictionaryService.refresh_asset(asset)

        assert SoftwareDictionary.objects.count() == 0


@pytest.mark.django_db
class TestSoftwareDictionaryServiceCleanupDelete:
    def test_cleanup_delete_decrements_and_removes_orphan_entry(
        self, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        SoftwareDictionaryService.refresh_asset(asset)
        entry = SoftwareDictionary.objects.get()
        entry_id = entry.id

        # deleting the asset triggers InventoryBase's pre_delete/post_delete
        # signals, which capture the M2M links then call cleanup_delete
        asset.delete()

        assert not SoftwareDictionary.objects.filter(id=entry_id).exists()

    def test_cleanup_delete_is_a_noop_with_no_entry_ids(
        self, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        SoftwareDictionaryService.refresh_asset(asset)

        # should not raise
        SoftwareDictionaryService.cleanup_delete(asset.id, [])
        SoftwareDictionaryService.cleanup_delete(None, [1, 2])

        assert SoftwareDictionary.objects.count() == 1

    def test_cleanup_delete_keeps_entry_still_used_by_other_assets(
        self, asset, section, software_fields, mapping, template
    ):
        other_asset = InventoryBase.objects.create(
            name="asset-2",
            description="desc",
            serial="SER-2",
            osname="Linux",
            osversion="1",
            uuid="uuid-asset-2",
            domain="example",
            agent="agent",
            template=template,
            is_template_forced=True,
        )
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        add_software_entry(
            other_asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        SoftwareDictionaryService.refresh_asset(asset)
        SoftwareDictionaryService.refresh_asset(other_asset)
        entry = SoftwareDictionary.objects.get()

        SoftwareDictionaryService.cleanup_delete(asset.id, [entry.id])

        entry.refresh_from_db()
        assert entry.installation_number == 1


@pytest.mark.django_db
class TestSoftwareDictionaryServiceVersionParsing:
    def test_legacy_template_splits_version_into_components(
        self, section, software_fields
    ):
        legacy_template = Template.objects.create(name="Legacy", os="LEG")
        SoftwareMapping.objects.create(
            template=legacy_template,
            section=section,
            name=software_fields["name"],
            publisher=software_fields["publisher"],
            version=software_fields["version"],
        )
        asset = InventoryBase.objects.create(
            name="legacy-asset",
            description="desc",
            serial="SER-4",
            osname="Linux",
            osversion="1",
            uuid="uuid-legacy-asset",
            domain="example",
            agent="agent",
            template=legacy_template,
            is_template_forced=True,
        )
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4.1",
        )

        SoftwareDictionaryService.refresh_asset(asset)

        entry = SoftwareDictionary.objects.get()
        assert entry.major_version == 2
        assert entry.minor_version == 4
        assert entry.patch_version == 1


@pytest.mark.django_db
class TestSoftwareDictionaryServiceGenerationMode:
    def test_default_generation_mode_is_inventory_when_unconfigured(self):
        assert SoftwareDictionaryService.get_generation_mode() == "inventory"
        assert SoftwareDictionaryService.should_refresh_on_inventory() is True
        assert SoftwareDictionaryService.should_refresh_on_automation() is False

    def test_generation_mode_reads_from_server_config(self):
        from config.models import Config

        server_config = Config.objects.get(name="server")
        server_config.value = [
            {"name": "software_dictionary_generation", "value": "automation"}
        ]
        server_config.save()

        assert SoftwareDictionaryService.get_generation_mode() == "automation"
        assert SoftwareDictionaryService.should_refresh_on_automation() is True


@pytest.mark.django_db
class TestSoftwareMappingApi:
    def test_create_mapping(self, api_client, template, section, software_fields):
        response = api_client.post(
            "/software_mapping/",
            {
                "template": template.id,
                "section": section.id,
                "name": software_fields["name"].id,
                "publisher": software_fields["publisher"].id,
                "version": software_fields["version"].id,
            },
            format="json",
        )

        assert response.status_code == 201
        assert SoftwareMapping.objects.filter(
            template=template, section=section
        ).exists()

    def test_create_requires_authentication(self):
        from rest_framework.test import APIClient

        response = APIClient().post("/software_mapping/", {}, format="json")

        assert response.status_code == 401


@pytest.mark.django_db
class TestSoftwareDictionaryApi:
    def test_list_returns_entries(
        self, api_client, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        SoftwareDictionaryService.refresh_asset(asset)

        response = api_client.get("/software_dictionary/")

        assert response.status_code == 200
        names = [entry["name"] for entry in response.data]
        assert "apache2" in names

    def test_search_filters_by_name(
        self, api_client, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )
        SoftwareDictionaryService.refresh_asset(asset)

        response = api_client.get("/software_dictionary/?search=apache")

        assert response.status_code == 200
        assert len(response.data) == 1


@pytest.mark.django_db
class TestSoftwareMappingIdentityFields:
    def test_mapping_accepts_identity_fields_from_other_sections(
        self, api_client, template, section, software_fields
    ):
        os_section = Section.objects.create(
            name="OS RELEASE", target="os-release", template=template
        )
        os_id = Field.objects.create(name="ID", section=os_section, order=1)
        architecture = Field.objects.create(
            name="ARCHITECTURE", section=section, order=4
        )

        response = api_client.post(
            "/software_mapping/",
            {
                "template": template.id,
                "section": section.id,
                "name": software_fields["name"].id,
                "architecture": architecture.id,
                "os_id": os_id.id,
            },
            format="json",
        )

        assert response.status_code == 201
        mapping = SoftwareMapping.objects.get(template=template)
        assert mapping.architecture == architecture
        assert mapping.os_id == os_id
        assert mapping.running_kernel is None

    def test_fields_can_be_filtered_by_template(
        self, api_client, template, section, software_fields
    ):
        os_section = Section.objects.create(
            name="OS RELEASE", target="os-release", template=template
        )
        Field.objects.create(name="ID", section=os_section, order=1)
        other_template = Template.objects.create(name="Other", os="WIN")
        other_section = Section.objects.create(
            name="SOFTWARES", target="softwares", template=other_template
        )
        Field.objects.create(name="NAME", section=other_section, order=1)

        response = api_client.get(f"/fields/?template={template.id}")

        assert response.status_code == 200
        assert sorted(field["name"] for field in response.data) == [
            "ID",
            "Name",
            "Publisher",
            "Version",
        ]


RELEASES = {
    ("debian", "bullseye"): "11",
    ("debian", "bookworm"): "12",
    ("debian", "trixie"): "13",
    ("ubuntu", "focal"): "20.04",
    ("ubuntu", "jammy"): "22.04",
    ("ubuntu", "noble"): "24.04",
}


@pytest.mark.parametrize(
    "os_id, os_like, os_release, os_codename, expected",
    [
        ("debian", "", "13", "trixie", ("deb", "debian:13")),
        ('"debian"', "", '"13"', "", ("deb", "debian:13")),
        ("debian", "", "12.5", "", ("deb", "debian:12")),
        ("debian", "", "", "bookworm", ("deb", "debian:12")),
        ("ubuntu", "debian", "24.04", "noble", ("deb", "ubuntu:24.04")),
        ("ubuntu", "debian", "22.04", "jammy", ("deb", "ubuntu:22.04")),
        ("pop", "ubuntu debian", "24.04", "noble", ("deb", "ubuntu:24.04")),
        ("linuxmint", "ubuntu debian", "22.3", "noble", ("deb", "ubuntu:24.04")),
        ("kali", "debian", "2026.3", "kali-rolling", ("deb", "")),
        ("rocky", "rhel centos fedora", "9.4", "", ("rpm", "rocky:9")),
        ("Ubuntu 20.04", "", "20.04", "", ("deb", "ubuntu:20.04")),
        ("CentOS Linux release 7.9.2009", "", "3.10.0", "", ("rpm", "centos:7")),
        ("Rocky Linux 9.4", "", "", "", ("rpm", "rocky:9")),
        (
            "Microsoft Windows 11 Professionnel",
            "",
            "10.0.26200",
            "",
            ("windows", "windows"),
        ),
        ("macOS", "", "26.1", "", ("macos", "macos")),
        ("Mac OS X", "", "10.15.7", "", ("macos", "macos")),
        ("", "", "", "", ("", "")),
        ("freebsd", "", "14.1", "", ("", "")),
        ("Debian GNU/Linux trixie/sid", "", "6.12.0", "", ("deb", "")),
        (
            "Debian GNU/Linux 12 (bookworm)",
            "",
            "6.1.0-18-amd64",
            "",
            ("deb", "debian:12"),
        ),
    ],
)
def test_resolve_platform(os_id, os_like, os_release, os_codename, expected):
    platform = resolve(os_id, os_like, os_release, os_codename, RELEASES)

    assert (platform.family, platform.key) == expected


@pytest.mark.django_db
class TestDistroRelease:
    def test_default_releases_are_seeded(self):
        assert DistroRelease.objects.filter(
            base="ubuntu", codename="noble", version="24.04"
        ).exists()
        assert DistroRelease.objects.count() == 6

    def test_api_lists_releases(self, api_client):
        response = api_client.get("/distro_releases/?base=debian")

        assert response.status_code == 200
        assert sorted(row["codename"] for row in response.data) == [
            "bookworm",
            "bullseye",
            "trixie",
        ]


OS_RELEASE_FIELDS = ("ID", "ID_LIKE", "VERSION_ID", "CODENAME", "RUNNING_KERNEL")


@pytest.fixture
def identity_fields(section, software_fields, template):
    os_section = Section.objects.create(
        name="OS RELEASE", target="os-release", template=template
    )
    fields = dict(software_fields)
    fields["architecture"] = Field.objects.create(
        name="ARCHITECTURE", section=section, order=4
    )
    fields["package_format"] = Field.objects.create(
        name="FROM", section=section, order=5
    )
    fields["source_package"] = Field.objects.create(
        name="SOURCE", section=section, order=6
    )
    for order, name in enumerate(OS_RELEASE_FIELDS, 1):
        fields[name] = Field.objects.create(name=name, section=os_section, order=order)
    fields["os_section"] = os_section
    return fields


@pytest.fixture
def identity_mapping(template, section, identity_fields):
    return SoftwareMapping.objects.create(
        template=template,
        section=section,
        name=identity_fields["name"],
        publisher=identity_fields["publisher"],
        version=identity_fields["version"],
        architecture=identity_fields["architecture"],
        package_format=identity_fields["package_format"],
        source_package=identity_fields["source_package"],
        os_id=identity_fields["ID"],
        os_like=identity_fields["ID_LIKE"],
        os_release=identity_fields["VERSION_ID"],
        os_codename=identity_fields["CODENAME"],
        running_kernel=identity_fields["RUNNING_KERNEL"],
    )


def make_asset(template, name):
    return InventoryBase.objects.create(
        name=name,
        description="desc",
        serial=f"SER-{name}",
        osname="Linux",
        osversion="1",
        uuid=f"uuid-{name}",
        domain="example",
        agent="agent",
        template=template,
        is_template_forced=True,
    )


def add_values(asset, section, values):
    inventory_section = InventorySection.objects.create(
        base=asset, template_section=section
    )
    for field, value in values.items():
        InventoryField.objects.create(
            inventory_section=inventory_section, template_field=field, value=value
        )


def add_package(asset, section, fields, name, version, source="openssl"):
    add_values(
        asset,
        section,
        {
            fields["name"]: name,
            fields["publisher"]: "",
            fields["version"]: version,
            fields["architecture"]: "amd64",
            fields["package_format"]: "deb",
            fields["source_package"]: source,
        },
    )


def add_os_release(asset, fields, os_id, os_like, release, codename):
    add_values(
        asset,
        fields["os_section"],
        {
            fields["ID"]: os_id,
            fields["ID_LIKE"]: os_like,
            fields["VERSION_ID"]: release,
            fields["CODENAME"]: codename,
            fields["RUNNING_KERNEL"]: "6.8.0-87-generic",
        },
    )


@pytest.mark.django_db
class TestSoftwareDictionaryPlatform:
    def test_entry_gets_platform_and_package_fields(
        self, template, section, identity_fields, identity_mapping
    ):
        asset = make_asset(template, "mint")
        add_os_release(
            asset, identity_fields, "linuxmint", "ubuntu debian", "22.3", "noble"
        )
        add_package(
            asset, section, identity_fields, "libssl3t64:amd64", "3.0.13-0ubuntu3.5"
        )

        SoftwareDictionaryService.refresh_asset(asset)

        entry = SoftwareDictionary.objects.get()
        assert entry.platform_family == "deb"
        assert entry.platform_key == "ubuntu:24.04"
        assert entry.architecture == "amd64"
        assert entry.package_format == "deb"
        assert entry.source_package == "openssl"
        platform = AssetPlatform.objects.get(asset=asset)
        assert (platform.family, platform.key) == ("deb", "ubuntu:24.04")
        assert platform.os_id == "linuxmint"
        assert platform.running_kernel == "6.8.0-87-generic"

    def test_values_longer_than_their_column_are_cut(
        self, template, section, identity_fields, identity_mapping
    ):
        asset = make_asset(template, "long-values")
        add_values(
            asset,
            identity_fields["os_section"],
            {identity_fields["VERSION_ID"]: "9" * 300},
        )
        add_values(
            asset,
            section,
            {
                identity_fields["name"]: "curl",
                identity_fields["architecture"]: "0123456789" * 10,
            },
        )

        SoftwareDictionaryService.refresh_asset(asset)

        stored = SoftwareDictionary.objects.get().architecture
        assert stored == ("0123456789" * 10)[:64]
        assert AssetPlatform.objects.get(asset=asset).os_release == "9" * 255

    def test_same_package_on_two_distributions_gives_two_entries(
        self, template, section, identity_fields, identity_mapping
    ):
        debian = make_asset(template, "debian")
        add_os_release(debian, identity_fields, "debian", "", "13", "trixie")
        add_package(debian, section, identity_fields, "curl", "8.14.1-2")
        ubuntu = make_asset(template, "ubuntu")
        add_os_release(ubuntu, identity_fields, "ubuntu", "debian", "24.04", "noble")
        add_package(ubuntu, section, identity_fields, "curl", "8.14.1-2")

        SoftwareDictionaryService.refresh_asset(debian)
        SoftwareDictionaryService.refresh_asset(ubuntu)

        assert sorted(
            SoftwareDictionary.objects.values_list("platform_key", flat=True)
        ) == ["debian:13", "ubuntu:24.04"]

    def test_windows_entries_stay_shared_across_os_versions(
        self, template, section, identity_fields, identity_mapping
    ):
        for name, caption in (
            ("win10", "Microsoft Windows 10 Professionnel"),
            ("win11", "Microsoft Windows 11 Professionnel"),
        ):
            asset = make_asset(template, name)
            add_os_release(asset, identity_fields, caption, "", "10.0", "")
            add_values(
                asset,
                section,
                {
                    identity_fields["name"]: "Mozilla Firefox (x64 fr)",
                    identity_fields["publisher"]: "Mozilla",
                    identity_fields["version"]: "154.0.1",
                },
            )
            SoftwareDictionaryService.refresh_asset(asset)

        entry = SoftwareDictionary.objects.get()
        assert entry.platform_key == "windows"
        assert entry.installation_number == 2

    def test_machine_field_uses_first_row(
        self, template, section, identity_fields, identity_mapping
    ):
        asset = make_asset(template, "two-rows")
        add_os_release(asset, identity_fields, "debian", "", "13", "trixie")
        add_os_release(asset, identity_fields, "ubuntu", "debian", "24.04", "noble")
        add_package(asset, section, identity_fields, "curl", "8.14.1-2")

        SoftwareDictionaryService.refresh_asset(asset)

        assert SoftwareDictionary.objects.get().platform_key == "debian:13"

    def test_platform_is_unknown_without_os_fields(
        self, asset, section, software_fields, mapping
    ):
        add_software_entry(
            asset,
            section,
            software_fields,
            name="apache2",
            publisher="Debian",
            version="2.4",
        )

        SoftwareDictionaryService.refresh_asset(asset)

        entry = SoftwareDictionary.objects.get()
        assert entry.platform_family is None
        assert entry.platform_key is None
        assert AssetPlatform.objects.get(asset=asset).family == ""

    def test_api_filters_by_platform(
        self, api_client, template, section, identity_fields, identity_mapping
    ):
        asset = make_asset(template, "debian")
        add_os_release(asset, identity_fields, "debian", "", "13", "trixie")
        add_package(asset, section, identity_fields, "curl", "8.14.1-2")
        SoftwareDictionaryService.refresh_asset(asset)

        response = api_client.get("/software_dictionary/?platform_key=debian:13")

        assert response.status_code == 200
        assert [row["source_package"] for row in response.data] == ["openssl"]
