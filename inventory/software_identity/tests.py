import tarfile

import pytest
from inventory.software_identity.conftest import FIXTURE_CPES, build_feed, fake_open
from inventory.software_identity.cpe.matcher import (
    CpeMatcher,
    version_signal,
    year_signal,
)
from inventory.software_identity.cpe.sync import sync_cpe_index
from inventory.software_identity.cpe.tokens import base_title, title_entries, tokens
from inventory.software_identity.match_key import match_key
from inventory.software_identity.models import CpeIndexState, CpeProduct, CpeToken
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


class TestLinuxNormalizer:
    def normalize(self, **values):
        record = SoftwareRecord(
            **{"platform_family": "deb", "platform_key": "ubuntu:24.04", **values}
        )
        return build_normalizers(None, {})[record.platform_family].normalize(record)

    def test_debian_purl(self):
        result = self.normalize(
            name="libssl3t64:amd64",
            version="3.0.13-0ubuntu3.5",
            architecture="amd64",
            package_format="deb",
            source_package="openssl",
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
