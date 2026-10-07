import tarfile

import pytest
from inventory.software_identity.conftest import FIXTURE_CPES, build_feed, fake_open
from inventory.software_identity.cpe.sync import sync_cpe_index
from inventory.software_identity.cpe.tokens import base_title, title_entries, tokens
from inventory.software_identity.models import CpeIndexState, CpeProduct, CpeToken


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
