import tarfile

import pytest
from automation.scheduler.models import Scheduler
from django.db import IntegrityError
from inventory.software.models import SoftwareDictionary
from inventory.software_identity.conftest import FIXTURE_CPES, build_feed, fake_open
from inventory.software_identity.cpe.matcher import (
    CpeMatcher,
    version_signal,
    year_signal,
)
from inventory.software_identity.cpe.sync import sync_cpe_index
from inventory.software_identity.cpe.tokens import base_title, title_entries, tokens
from inventory.software_identity.match_key import match_key
from inventory.software_identity.models import (
    CpeIndexState,
    CpeProduct,
    CpeToken,
    IdentityDecision,
    PackageOrigin,
    SoftwareIdentity,
)
from inventory.software_identity.normalizers import build_normalizers
from inventory.software_identity.normalizers.base import (
    MATCHED,
    NONE,
    REVIEW,
    UNSUPPORTED,
    VALIDATED,
    EffectiveDecision,
    SoftwareRecord,
)
from inventory.software_identity.normalizers.cpe import cpe_identifier
from inventory.software_identity.services import IdentityService


def test_tokens_drop_versions_architectures_and_parentheses():
    assert tokens("Mozilla Firefox (x64 fr) 154.0.1") == ["mozilla", "firefox"]
    assert tokens("Notepad++ (64-bit x64)") == ["notepad++"]
    assert tokens("7-Zip 24.08") == ["7", "zip"]


def test_base_title_removes_the_version():
    assert base_title("Mozilla Firefox 154.0.1", "154.0.1") == "mozilla firefox"
    assert base_title("Microsoft Edge Chromium 152.0.4191.66", "152.0.4191.66") == (
        "microsoft edge chromium"
    )


def test_title_entries_keep_vendor_words_that_name_the_product():
    vendor_words, entries = title_entries("git-scm", "git", ["git-scm git"])

    assert vendor_words == {"scm"}
    assert entries == [frozenset({"git", "scm"})]


@pytest.mark.django_db
class TestCpeIndexSync:
    def test_sync_builds_products_titles_and_versions(self, cpe_index):
        firefox = CpeProduct.objects.get(vendor="mozilla", product="firefox")
        assert firefox.titles == {"mozilla firefox": 2}
        assert firefox.versions == ["150.0", "154.0.1"]
        assert firefox.popularity == 2
        assert CpeProduct.objects.filter(
            vendor="notepad-plus-plus", product="notepad++"
        ).exists()

    def test_sync_skips_deprecated_and_non_application_names(self, cpe_index):
        assert not CpeProduct.objects.filter(product="oldproduct").exists()
        assert not CpeProduct.objects.filter(product="windows_11").exists()

    def test_rare_words_weigh_more(self, cpe_index):
        edge = (
            CpeToken.objects.filter(token="edge")
            .values_list("weight", flat=True)
            .first()
        )
        microsoft = (
            CpeToken.objects.filter(token="microsoft")
            .values_list("weight", flat=True)
            .first()
        )
        assert edge > microsoft

    def test_sync_records_state_and_skips_an_unchanged_feed(self, cpe_index):
        state = CpeIndexState.current()
        assert state.version == 1
        assert state.product_count == CpeProduct.objects.count() == 13
        assert state.source_date == "2026-10-06T23:50:00-04:00"

        assert sync_cpe_index(open_url=fake_open(build_feed())) is False
        assert CpeIndexState.current().version == 1

    def test_failed_sync_keeps_previous_index(self, cpe_index):
        broken = fake_open(b"not a tar archive", sha="1" * 64)

        with pytest.raises(tarfile.ReadError):
            sync_cpe_index(open_url=broken)

        assert CpeIndexState.current().version == 1
        assert CpeProduct.objects.count() == 13

    def test_changed_feed_rebuilds_the_index(self, cpe_index):
        feed = build_feed(
            FIXTURE_CPES
            + [("a", "mozilla", "firefox", "155.0", "Mozilla Firefox 155.0", False)]
        )

        assert sync_cpe_index(open_url=fake_open(feed, sha="2" * 64)) is True

        assert CpeIndexState.current().version == 2
        firefox = CpeProduct.objects.get(vendor="mozilla", product="firefox")
        assert "155.0" in firefox.versions

    def test_feed_without_application_is_refused(self, cpe_index):
        feed = build_feed([FIXTURE_CPES[-1]])

        with pytest.raises(ValueError):
            sync_cpe_index(open_url=fake_open(feed, sha="3" * 64))

        assert CpeIndexState.current().version == 1
        assert CpeProduct.objects.count() == 13

    def test_collapsed_feed_is_refused(self, cpe_index):
        feed = build_feed(FIXTURE_CPES[:1])

        with pytest.raises(ValueError):
            sync_cpe_index(open_url=fake_open(feed, sha="4" * 64))

        assert CpeIndexState.current().version == 1
        assert CpeProduct.objects.count() == 13


def test_version_signal_levels():
    known = ["152.0.4191.66", "151.0.1"]
    assert version_signal("152.0.4191.66", known) == 0.15
    assert version_signal("152.0.4191.53", known) == 0.12
    assert version_signal("152.1", known) == 0.05
    assert version_signal("97.0", known) is None
    assert version_signal("", known) == 0.0


def test_year_signal():
    assert year_signal("visual_studio_2026", "Visual Studio Community 2026") == 0.1
    assert year_signal("visual_studio_2022", "Visual Studio Community 2026") == -0.3
    assert year_signal("visual_studio_2022", "Visual Studio Community") == -0.1
    assert year_signal("visual_studio_community", "Visual Studio Community 2026") == 0.0


@pytest.mark.django_db
class TestCpeMatcher:
    @pytest.mark.parametrize(
        "name, publisher, version, expected",
        [
            (
                "Mozilla Firefox (x64 fr)",
                "Mozilla",
                "154.0.1",
                "mozilla:firefox",
            ),
            (
                "Firefox",
                "Identified Developer",
                "149.0.2",
                "mozilla:firefox",
            ),
            (
                "Microsoft Edge",
                "Microsoft Corporation",
                "152.0.4191.53",
                "microsoft:edge_chromium",
            ),
            (
                "Visual Studio Community 2026",
                "Microsoft Corporation",
                "18.9.2",
                "microsoft:visual_studio_2026",
            ),
            (
                "Notepad++ (64-bit x64)",
                "Notepad++ Team",
                "8.9.8",
                "notepad-plus-plus:notepad++",
            ),
            (
                "7-Zip 24.08 (x64)",
                "Igor Pavlov",
                "24.08",
                "7-zip:7-zip",
            ),
            (
                "Git",
                "The Git Development Community",
                "2.55.0.5",
                "git-scm:git",
            ),
        ],
    )
    def test_best_candidate(self, cpe_index, name, publisher, version, expected):
        ranked = CpeMatcher().rank(name, publisher, version)

        assert ranked[0][1] == expected

    def test_unknown_name_has_no_candidate(self, cpe_index):
        assert CpeMatcher().rank("Kyber", "Kyber SAS", "1.2") == []

    def test_candidate_limit_bounds_the_products_loaded(self, cpe_index):
        assert (
            len(CpeMatcher(candidate_limit=1).rank("Microsoft Edge", "", "152.0"))
            == 1
        )

    def test_no_index_is_not_available(self, db):
        assert CpeMatcher().available is False


class FakeMatcher:
    def __init__(self, ranked):
        self.ranked = ranked
        self.calls = 0

    def rank(self, name, publisher, version, limit=5):
        self.calls += 1
        return self.ranked


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Mozilla Firefox (x64 fr)", "mozilla firefox"),
        ("Ivanti Secure Access Client 22.6", "ivanti secure access client"),
        (
            "Microsoft Visual C++ 2015-2022 Redistributable (x64) - 14.51.36231",
            "microsoft visual c++ 2015-2022 redistributable",
        ),
        ("Visual Studio Community 2026", "visual studio community 2026"),
        (
            "Microsoft .NET SDK 10.0.400 (x64) from Visual Studio",
            "microsoft .net sdk from visual studio",
        ),
    ],
)
def test_match_key(name, expected):
    assert match_key(name) == expected


def windows_record(
    name="Microsoft Edge", version="152.0.4191.53", publisher="Microsoft"
):
    return SoftwareRecord(
        name=name,
        publisher=publisher,
        version=version,
        platform_family="windows",
        platform_key="windows",
    )


class TestCpeNormalizers:
    def test_decision_wins_without_calling_the_matcher(self):
        matcher = FakeMatcher([(1.2, "microsoft:edge")])
        decisions = {
            ("windows", "microsoft edge"): EffectiveDecision(
                7, "microsoft:edge_chromium"
            )
        }

        result = build_normalizers(matcher, decisions)["windows"].normalize(
            windows_record()
        )

        assert result.status == VALIDATED
        assert result.decision_id == 7
        assert result.identifier == (
            "cpe:2.3:a:microsoft:edge_chromium:152.0.4191.53:*:*:*:*:*:*:*"
        )
        assert matcher.calls == 0

    def test_decision_for_no_cpe(self):
        decisions = {("windows", "microsoft edge"): EffectiveDecision(8, None)}

        result = build_normalizers(FakeMatcher([]), decisions)["windows"].normalize(
            windows_record()
        )

        assert (result.status, result.reason, result.decision_id) == (
            NONE,
            "decided_none",
            8,
        )

    @pytest.mark.parametrize(
        "ranked, status",
        [
            ([(0.95, "a:b"), (0.80, "c:d")], MATCHED),
            ([(0.95, "a:b"), (0.90, "c:d")], REVIEW),
            ([(0.60, "a:b")], REVIEW),
            ([(0.40, "a:b")], NONE),
            ([], NONE),
        ],
    )
    def test_thresholds(self, ranked, status):
        result = build_normalizers(FakeMatcher(ranked), {})["windows"].normalize(
            windows_record()
        )

        assert result.status == status
        assert len(result.candidates) == min(len(ranked), 3)

    def test_identifier_escaping_and_version_cleaning(self):
        assert cpe_identifier("notepad-plus-plus:notepad++", "8.9.8") == (
            r"cpe:2.3:a:notepad-plus-plus:notepad\+\+:8.9.8:*:*:*:*:*:*:*"
        )
        result = build_normalizers(FakeMatcher([(1.0, "tunnelblick:tunnelblick")]), {})[
            "macos"
        ].normalize(
            SoftwareRecord(
                name="Tunnelblick",
                publisher="Identified Developer",
                version="4.0.1 (build 5971)",
                platform_family="macos",
                platform_key="macos",
            )
        )
        assert result.version == "4.0.1"
        assert (
            cpe_identifier("apple:pages", "") == "cpe:2.3:a:apple:pages:*:*:*:*:*:*:*:*"
        )

    def test_macos_apple_applications_are_os_components(self):
        matcher = FakeMatcher([(1.0, "synology:contacts")])
        normalizer = build_normalizers(matcher, {})["macos"]

        result = normalizer.normalize(
            SoftwareRecord(
                name="Contacts",
                publisher="Apple",
                version="14.0",
                platform_family="macos",
                platform_key="macos",
            )
        )

        assert (result.status, result.reason) == (UNSUPPORTED, "os_component")
        assert matcher.calls == 0

    @pytest.mark.django_db
    def test_with_the_real_matcher(self, cpe_index):
        normalizers = build_normalizers(CpeMatcher(), {})

        firefox = normalizers["windows"].normalize(
            windows_record("Mozilla Firefox (x64 fr)", "154.0.1", "Mozilla")
        )
        pages = normalizers["macos"].normalize(
            SoftwareRecord(
                name="Pages",
                publisher="App Store",
                version="13.1",
                platform_family="macos",
                platform_key="macos",
            )
        )
        assert (firefox.status, firefox.product) == (MATCHED, "mozilla:firefox")
        assert (pages.status, pages.product) == (MATCHED, "apple:pages")


ORIGINS = {
    "ubuntu": "ubuntu",
    "rocky enterprise software foundation": "rocky",
    "red hat, inc.": "redhat",
}


class TestLinuxNormalizer:
    def normalize(self, **values):
        record = SoftwareRecord(
            **{"platform_family": "deb", "platform_key": "ubuntu:24.04", **values}
        )
        normalizers = build_normalizers(None, {}, ORIGINS)
        return normalizers[record.platform_family].normalize(record)

    def test_debian_purl(self):
        result = self.normalize(
            name="libssl3t64:amd64",
            version="3.0.13-0ubuntu3.5",
            architecture="amd64",
            package_format="deb",
            source_package="openssl",
            package_origin="Ubuntu",
        )

        assert result.status == MATCHED
        assert result.identifier == (
            "pkg:deb/ubuntu/openssl@3.0.13-0ubuntu3.5?arch=amd64&distro=ubuntu-24.04"
        )
        assert result.product == "pkg:deb/ubuntu/openssl"
        assert result.match_key == "openssl"
        assert result.reason == ""

    def test_rpm_epoch_goes_in_a_qualifier(self):
        result = self.normalize(
            name="openssl",
            version="1:3.0.7-27.el9",
            architecture="x86_64",
            source_package="openssl",
            platform_family="rpm",
            platform_key="rocky:9",
        )

        assert result.identifier == (
            "pkg:rpm/rocky/openssl@3.0.7-27.el9?arch=x86_64&distro=rocky-9&epoch=1"
        )
        assert result.version == "1:3.0.7-27.el9"

    def test_rpm_names_keep_their_case(self):
        result = self.normalize(
            name="NetworkManager",
            version="1.46.0-8.el9",
            source_package="NetworkManager",
            platform_family="rpm",
            platform_key="rocky:9",
        )

        assert result.product == "pkg:rpm/rocky/NetworkManager"
        assert result.match_key == "networkmanager"

    def test_source_falls_back_on_the_binary_name(self):
        result = self.normalize(name="curl:amd64", version="8.5.0-2ubuntu10.13")

        assert result.product == "pkg:deb/ubuntu/curl"
        assert result.reason == "source_not_mapped"

    def test_snap_packages_are_not_covered(self):
        result = self.normalize(name="firefox", version="150.0", package_format="snap")

        assert (result.status, result.reason) == (UNSUPPORTED, "package_format")

    def test_unknown_release_is_not_covered(self):
        result = self.normalize(name="curl", version="8.5.0", platform_key="")

        assert (result.status, result.reason) == (UNSUPPORTED, "unknown_release")

    @pytest.mark.parametrize(
        "family, key, origin, status, reason, product, distro",
        [
            (
                "rpm",
                "rocky:9",
                "Rocky Enterprise Software Foundation",
                MATCHED,
                "",
                "pkg:rpm/rocky/openssl",
                "distro=rocky-9",
            ),
            ("rpm", "rocky:9", "Fedora Project", UNSUPPORTED, "third_party", "", ""),
            ("rpm", "rocky:9", "", UNSUPPORTED, "no_origin", "", ""),
            (
                "rpm",
                "almalinux:9",
                "Red Hat, Inc.",
                MATCHED,
                "",
                "pkg:rpm/redhat/openssl",
                "distro=almalinux-9",
            ),
            (
                "deb",
                "ubuntu:24.04",
                "Ubuntu",
                MATCHED,
                "",
                "pkg:deb/ubuntu/openssl",
                "distro=ubuntu-24.04",
            ),
            ("deb", "ubuntu:24.04", "linuxmint", UNSUPPORTED, "third_party", "", ""),
            ("deb", "ubuntu:22.04", "Docker", UNSUPPORTED, "third_party", "", ""),
            (
                "deb",
                "ubuntu:20.04",
                None,
                MATCHED,
                "origin_not_mapped",
                "pkg:deb/ubuntu/openssl",
                "distro=ubuntu-20.04",
            ),
        ],
    )
    def test_package_origin(self, family, key, origin, status, reason, product, distro):
        result = self.normalize(
            name="openssl",
            version="3.0.7-27",
            source_package="openssl",
            platform_family=family,
            platform_key=key,
            package_origin=origin,
        )

        assert (result.status, result.reason, result.product) == (
            status,
            reason,
            product,
        )
        assert distro in result.identifier
        assert result.match_key == "openssl"

    def test_missing_source_is_reported_before_missing_origin(self):
        result = self.normalize(
            name="curl", version="7.68.0-1ubuntu2.25", platform_key="ubuntu:20.04"
        )

        assert (result.status, result.reason) == (MATCHED, "source_not_mapped")
        assert result.product == "pkg:deb/ubuntu/curl"

    def test_origin_is_compared_without_case_and_spaces(self):
        result = self.normalize(
            name="curl", version="8", source_package="curl", package_origin="  UBUNTU "
        )

        assert (result.status, result.product) == (MATCHED, "pkg:deb/ubuntu/curl")

    def test_unknown_release_comes_before_the_origin(self):
        result = self.normalize(
            name="curl", version="8", platform_key="", package_origin="Docker"
        )

        assert (result.status, result.reason) == (UNSUPPORTED, "unknown_release")


def make_entry(name, version, family, key, installations=1, **values):
    return SoftwareDictionary.objects.create(
        name=name,
        publisher=values.pop("publisher", ""),
        version=version,
        platform_family=family,
        platform_key=key,
        installation_number=installations,
        **values,
    )


@pytest.mark.django_db
class TestIdentityService:
    def test_seeds(self):
        tasks = Scheduler.objects.filter(
            name__in=["cpeIndex.CpeIndexSync", "softwareIdentity.SoftwareIdentity"]
        )
        assert sorted(tasks.values_list("recurrence", "active")) == [
            ("daily", False),
            ("hourly", False),
        ]
        assert IdentityDecision.objects.filter(source="shipped").count() == 6
        origins = dict(PackageOrigin.objects.values_list("name", "distribution"))
        assert origins == {
            "Debian": "debian",
            "Ubuntu": "ubuntu",
            "Rocky Enterprise Software Foundation": "rocky",
            "AlmaLinux": "almalinux",
            "Red Hat, Inc.": "redhat",
            "CentOS": "centos",
        }

    def test_origin_names_are_unique_without_case(self):
        with pytest.raises(IntegrityError):
            PackageOrigin.objects.create(name="ubuntu", distribution="ubuntu")

    def test_linux_entries_are_identified_without_index(self):
        entry = make_entry(
            "curl", "8.14.1-2", "deb", "debian:13", source_package="curl"
        )

        counts = IdentityService.refresh()

        identity = SoftwareIdentity.objects.get(entry=entry)
        assert identity.status == "matched"
        assert identity.identifier == "pkg:deb/debian/curl@8.14.1-2?distro=debian-13"
        assert counts["matched"] == 1

    def test_cpe_entries_wait_for_an_index(self):
        make_entry("Mozilla Firefox (x64 fr)", "154.0.1", "windows", "windows")

        counts = IdentityService.refresh()

        assert SoftwareIdentity.objects.count() == 0
        assert counts == {"pending": 1}

    def test_unknown_platform_is_not_covered(self):
        entry = make_entry("apache2", "2.4", None, None)

        IdentityService.refresh()

        identity = SoftwareIdentity.objects.get(entry=entry)
        assert (identity.status, identity.reason) == ("unsupported", "unknown_platform")

    def test_windows_entries_use_the_index_and_shipped_decisions(self, cpe_index):
        firefox = make_entry(
            "Mozilla Firefox (x64 fr)",
            "154.0.1",
            "windows",
            "windows",
            publisher="Mozilla",
        )
        edge = make_entry("Microsoft Edge", "152.0.4191.53", "windows", "windows")

        IdentityService.refresh()

        firefox_identity = SoftwareIdentity.objects.get(entry=firefox)
        assert (firefox_identity.status, firefox_identity.product) == (
            "matched",
            "mozilla:firefox",
        )
        assert firefox_identity.index_version == 1
        edge_identity = SoftwareIdentity.objects.get(entry=edge)
        assert (edge_identity.status, edge_identity.product) == (
            "validated",
            "microsoft:edge_chromium",
        )
        assert edge_identity.decision.source == "shipped"

    def test_a_new_index_recomputes_undecided_identities_only(self, cpe_index):
        make_entry("Mozilla Firefox (x64 fr)", "154.0.1", "windows", "windows")
        make_entry("Microsoft Edge", "152.0.4191.53", "windows", "windows")
        IdentityService.refresh()
        sync_cpe_index(open_url=fake_open(build_feed(), sha="9" * 64))

        counts = IdentityService.refresh()

        assert counts == {"matched": 1}
        versions = SoftwareIdentity.objects.values_list("index_version", flat=True)
        assert set(versions) == {1, 2}

    def test_decide_applies_to_every_version(self, cpe_index, admin_user):
        old = make_entry("Notepad++", "7", "windows", "windows")
        new = make_entry("Notepad++ (64-bit x64)", "8.9.8", "windows", "windows")
        IdentityService.refresh()

        IdentityService.decide(
            "windows", "notepad++", "notepad-plus-plus:notepad++", admin_user
        )

        identifiers = dict(
            SoftwareIdentity.objects.values_list("entry_id", "identifier")
        )
        assert (
            identifiers[old.id]
            == r"cpe:2.3:a:notepad-plus-plus:notepad\+\+:7:*:*:*:*:*:*:*"
        )
        assert (
            identifiers[new.id]
            == r"cpe:2.3:a:notepad-plus-plus:notepad\+\+:8.9.8:*:*:*:*:*:*:*"
        )
        assert set(SoftwareIdentity.objects.values_list("status", flat=True)) == {
            "validated"
        }

    def test_revert_falls_back_on_the_shipped_decision(self, cpe_index, admin_user):
        entry = make_entry("Microsoft Edge", "152.0.4191.53", "windows", "windows")
        IdentityService.refresh()
        decision = IdentityService.decide("windows", "microsoft edge", None, admin_user)
        assert SoftwareIdentity.objects.get(entry=entry).status == "none"

        IdentityService.revert(decision)

        identity = SoftwareIdentity.objects.get(entry=entry)
        assert (identity.status, identity.decision.source) == ("validated", "shipped")

    def test_shipped_decisions_cannot_be_reverted(self):
        decision = IdentityDecision.objects.filter(source="shipped").first()

        with pytest.raises(ValueError):
            IdentityService.revert(decision)

    def test_decide_and_revert_without_index(self, admin_user):
        entry = make_entry("Kyber", "1.2", "windows", "windows")

        decision = IdentityService.decide("windows", "kyber", None, admin_user)
        IdentityService.refresh()
        assert SoftwareIdentity.objects.get(entry=entry).status == "none"

        IdentityService.revert(decision)
        assert not SoftwareIdentity.objects.filter(entry=entry).exists()

    def test_one_failing_entry_does_not_stop_the_run(self, monkeypatch):
        good = make_entry("curl", "8.14.1-2", "deb", "debian:13")
        bad = make_entry("broken", "1", "deb", "debian:13")
        original = IdentityService._normalize

        def flaky(entry, normalizers, matcher):
            if entry.id == bad.id:
                raise RuntimeError("boom")
            return original(entry, normalizers, matcher)

        monkeypatch.setattr(IdentityService, "_normalize", staticmethod(flaky))

        counts = IdentityService.refresh()

        assert counts == {"matched": 1, "error": 1}
        assert SoftwareIdentity.objects.filter(entry=good).exists()

    def test_a_failing_save_does_not_stop_the_run(self, monkeypatch):
        good = make_entry("curl", "8.14.1-2", "deb", "debian:13")
        bad = make_entry("broken", "1", "deb", "debian:13")
        original = IdentityService._save

        def flaky(entry, result, index_version):
            if entry.id == bad.id:
                raise IntegrityError("boom")
            return original(entry, result, index_version)

        monkeypatch.setattr(IdentityService, "_save", staticmethod(flaky))

        counts = IdentityService.refresh()

        assert counts == {"matched": 1, "error": 1}
        assert SoftwareIdentity.objects.filter(entry=good).exists()
        assert not SoftwareIdentity.objects.filter(entry=bad).exists()

    def test_a_long_name_is_stored_with_a_match_key_that_fits(self, cpe_index):
        entry = make_entry("x" * 300, "1", "windows", "windows")

        IdentityService.refresh()

        identity = SoftwareIdentity.objects.get(entry=entry)
        assert len(identity.match_key) == 255

    def test_a_new_index_keeps_unchanged_identities_untouched(self, cpe_index):
        entry = make_entry(
            "Mozilla Firefox (x64 fr)",
            "154.0.1",
            "windows",
            "windows",
            publisher="Mozilla",
        )
        IdentityService.refresh()
        before = SoftwareIdentity.objects.get(entry=entry)
        sync_cpe_index(open_url=fake_open(build_feed(), sha="9" * 64))

        IdentityService.refresh()

        after = SoftwareIdentity.objects.get(entry=entry)
        assert before.index_version == 1
        assert after.index_version == 2
        assert after.updated_at == before.updated_at


def make_identity(entry, status, match_key, candidates=None, family="windows"):
    return SoftwareIdentity.objects.create(
        entry=entry,
        family=family,
        match_key=match_key,
        status=status,
        candidates=candidates or [],
    )


@pytest.mark.django_db
class TestIdentityApi:
    def test_review_groups_versions_and_sorts_by_machines(self, api_client):
        small = make_entry("WinFsp 2025", "2.0", "windows", "windows", installations=1)
        make_identity(small, "review", "winfsp 2025")
        v1 = make_entry("Insomnia", "9.1.1", "windows", "windows", installations=3)
        v2 = make_entry("Insomnia", "9.2.0", "windows", "windows", installations=5)
        make_identity(
            v1, "review", "insomnia", [{"product": "konghq:insomnia", "score": 0.6}]
        )
        make_identity(
            v2, "review", "insomnia", [{"product": "konghq:insomnia", "score": 0.7}]
        )

        response = api_client.get("/software_identities/review/?limit=10")

        assert response.status_code == 200
        first = response.data["results"][0]
        assert (first["match_key"], first["entries"], first["machines"]) == (
            "insomnia",
            2,
            8,
        )
        assert first["candidates"] == [{"product": "konghq:insomnia", "score": 0.7}]
        assert response.data["count"] == 2

    def test_summary(self, api_client):
        make_identity(
            make_entry("curl", "8", "deb", "debian:13"),
            "matched",
            "curl",
            family="deb",
        )
        make_entry("waiting", "1", "windows", "windows")

        response = api_client.get("/software_identities/summary/")

        assert response.status_code == 200
        assert response.data["counts"] == [
            {"family": "deb", "status": "matched", "count": 1}
        ]
        assert response.data["pending"] == 1
        assert response.data["index"]["version"] == 0

    def test_create_decision_applies_it(self, api_client, cpe_index):
        entry = make_entry("Insomnia", "9.1.1", "windows", "windows")
        IdentityService.refresh()
        assert SoftwareIdentity.objects.get(entry=entry).status == "none"
        CpeProduct.objects.create(vendor="konghq", product="insomnia")

        response = api_client.post(
            "/software_identity_decisions/",
            {
                "family": "windows",
                "match_key": "insomnia",
                "product": "konghq:insomnia",
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["source"] == "admin"
        assert SoftwareIdentity.objects.get(entry=entry).status == "validated"

    def test_decision_on_an_unknown_product_is_rejected(self, api_client, cpe_index):
        response = api_client.post(
            "/software_identity_decisions/",
            {
                "family": "windows",
                "match_key": "insomnia",
                "product": "nobody:nothing",
            },
            format="json",
        )

        assert response.status_code == 400

    def test_decision_without_product_is_rejected(self, api_client):
        response = api_client.post(
            "/software_identity_decisions/",
            {"family": "windows", "match_key": "x"},
            format="json",
        )

        assert response.status_code == 400
        assert not IdentityDecision.objects.filter(match_key="x").exists()

    def test_decision_with_a_null_product_means_no_cpe(self, api_client):
        response = api_client.post(
            "/software_identity_decisions/",
            {"family": "windows", "match_key": "x", "product": None},
            format="json",
        )

        assert response.status_code == 201
        assert IdentityDecision.objects.get(match_key="x").product is None

    def test_shipped_decisions_cannot_be_deleted(self, api_client):
        shipped = IdentityDecision.objects.filter(source="shipped").first()

        response = api_client.delete(f"/software_identity_decisions/{shipped.id}/")

        assert response.status_code == 400
        assert IdentityDecision.objects.filter(id=shipped.id).exists()

    def test_admin_decisions_can_be_deleted(self, api_client, admin_user):
        decision = IdentityService.decide("windows", "kyber", None, admin_user)

        response = api_client.delete(f"/software_identity_decisions/{decision.id}/")

        assert response.status_code == 204

    def test_permissions(self, make_api_client):
        viewer = make_api_client("view_softwareidentity", "view_identitydecision")

        assert viewer.get("/software_identities/review/").status_code == 200
        assert (
            viewer.post(
                "/software_identity_decisions/",
                {"family": "windows", "match_key": "x", "product": None},
                format="json",
            ).status_code
            == 403
        )

    def test_cpe_products_search(self, api_client, cpe_index):
        response = api_client.get("/cpe_products/?search=edge")

        assert response.status_code == 200
        assert {row["key"] for row in response.data} == {
            "microsoft:edge",
            "microsoft:edge_chromium",
        }

    def test_dictionary_shows_and_filters_identity(self, api_client):
        entry = make_entry("curl", "8", "deb", "debian:13")
        make_identity(entry, "matched", "curl", family="deb")
        make_entry("waiting", "1", "windows", "windows")

        response = api_client.get("/software_dictionary/?identity__status=matched")

        assert response.status_code == 200
        assert [row["identity_status"] for row in response.data] == ["matched"]
        everything = api_client.get("/software_dictionary/")
        assert {row["identity_status"] for row in everything.data} == {
            "matched",
            None,
        }
