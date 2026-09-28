from unittest.mock import patch

import pytest
from asset.inventory_base.models import InventoryBase
from inventory.software.models import SoftwareDictionary
from inventory.template.models import Template

from .config import get_cve_config
from .models import CpeMatch, CveReport
from .serializers import CveReportSerializer
from .services import (
    _cve_affects_version,
    _cve_version_match_status,
    _is_placeholder_cpe,
    _parse_published_date,
    _parse_semver,
    _parse_vulnerability_lookup_response,
    _query_cpe_guesser,
    build_cve_summary,
    build_cve_url,
    clean_tokens,
    enrich_software,
    fetch_and_store_cves,
    fetch_cves,
    installed_version_display,
)


@pytest.fixture
def template(db):
    return Template.objects.create(name="Debian", os="DEB")


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
        is_template_forced=True,
    )


@pytest.fixture
def software(db):
    return SoftwareDictionary.objects.create(
        name="OpenSSL",
        publisher="OpenSSL Software Foundation",
        version="1.1.1",
        major_version=1,
        minor_version=1,
        installation_number=1,
    )


# --- Token cleaning -------------------------------------------------------


def test_clean_tokens_strips_noise_and_versions():
    assert clean_tokens("libmagic1") == ["libmagic"]
    assert "http" not in clean_tokens("http://example.org/some-tool")
    assert "org" not in clean_tokens("http://example.org/some-tool")


def test_clean_tokens_strips_parentheses_and_numeric_tokens():
    tokens = clean_tokens("7-Zip (x64) 19.00")
    assert "x64" not in tokens
    assert "19" not in tokens and "00" not in tokens


def test_clean_tokens_debian_arch_and_lib_prefix_suffix():
    tokens = clean_tokens("node-foo-bar")
    assert "node" not in tokens
    assert "foo" in tokens and "bar" in tokens

    tokens = clean_tokens("libssl3")
    assert tokens == ["libssl"]


# --- Placeholder filter ----------------------------------------------------


def test_placeholder_cpe_rejected():
    assert _is_placeholder_cpe("any_hostname_project", "any_hostname") is True
    assert _is_placeholder_cpe("any", "something") is True
    assert _is_placeholder_cpe("openssl", "openssl") is False


# --- cpe-guesser HTTP contract ---------------------------------------------


def test_query_cpe_guesser_parses_real_response_shape():
    """
    cpe-guesser's /search returns a list of [score, cpe_prefix] pairs (not
    objects with "cpe"/"rank" keys), highest score first. Placeholder
    candidates further down the list must be skipped in favor of the next
    real one.
    """
    fake_response = [
        [674.0, "cpe:2.3:a:openssl:openssl"],
        [166.0, "cpe:2.3:a:sfackler:openssl"],
    ]

    class FakeResponse:
        status_code = 200
        text = "..."

        def json(self):
            return fake_response

    with patch("security.services.requests.post", return_value=FakeResponse()) as mocked_post:
        cpe, rank = _query_cpe_guesser("http://cpe-guesser.example", ["openssl"])

    mocked_post.assert_called_once_with(
        "http://cpe-guesser.example/search", json={"query": ["openssl"]}, timeout=5
    )
    assert cpe == "cpe:2.3:a:openssl:openssl"
    assert rank == 674.0


def test_query_cpe_guesser_skips_placeholder_candidates():
    fake_response = [
        [50.0, "cpe:2.3:a:any_hostname_project:any_hostname"],
        [10.0, "cpe:2.3:a:openssl:openssl"],
    ]

    class FakeResponse:
        status_code = 200
        text = "..."

        def json(self):
            return fake_response

    with patch("security.services.requests.post", return_value=FakeResponse()):
        cpe, rank = _query_cpe_guesser("http://cpe-guesser.example", ["openssl"])

    assert cpe == "cpe:2.3:a:openssl:openssl"
    assert rank == 10.0


# --- Confidence threshold ---------------------------------------------------


@pytest.fixture
def cve_config():
    return {
        "vulnerability_lookup_url": "http://vuln-lookup.example/api",
        "cpe_guesser_url": "http://cpe-guesser.example",
        "min_confidence_rank": 100,
        "cache_validity_hours": 24,
    }


def test_below_threshold_sets_pending_review_without_fetching_cves(software, cve_config):
    with (
        patch("security.services.get_cve_config", return_value=cve_config),
        patch(
            "security.services.guess_cpe",
            return_value=("cpe:2.3:a:openssl:openssl:1.1.1:*:*:*:*:*:*:*", 50),
        ),
        patch("security.services.fetch_and_store_cves") as mocked_fetch,
    ):
        enrich_software(software)

    cpe_match = CpeMatch.objects.get(software=software)
    assert cpe_match.status == CpeMatch.STATUS_PENDING_REVIEW
    mocked_fetch.assert_not_called()
    assert CveReport.objects.filter(software=software).count() == 0


def test_above_threshold_confirms_and_fetches_cves(software, cve_config):
    with (
        patch("security.services.get_cve_config", return_value=cve_config),
        patch(
            "security.services.guess_cpe",
            return_value=("cpe:2.3:a:openssl:openssl:1.1.1:*:*:*:*:*:*:*", 150),
        ),
        patch("security.services.fetch_and_store_cves") as mocked_fetch,
    ):
        enrich_software(software)

    cpe_match = CpeMatch.objects.get(software=software)
    assert cpe_match.status == CpeMatch.STATUS_CONFIRMED
    mocked_fetch.assert_called_once()


# --- Non-regression: human decisions are never touched, auto-confirmed CVEs keep refreshing --


@pytest.mark.parametrize(
    "status,source",
    [
        (CpeMatch.STATUS_CONFIRMED, CpeMatch.SOURCE_MANUAL),
        (CpeMatch.STATUS_REJECTED, CpeMatch.SOURCE_AUTO),
        (CpeMatch.STATUS_REJECTED, CpeMatch.SOURCE_MANUAL),
    ],
)
def test_enrichment_task_never_reprocesses_human_decisions(software, status, source):
    """
    A human decision (manually confirmed CPE, or any rejection) is frozen
    forever: the task must never call enrich_software() for it again.
    """
    existing = CpeMatch.objects.create(
        software=software,
        cpe="cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*",
        cpe_rank=10,
        source=source,
        status=status,
    )

    from automation.tasks.cveEnrichment import CveEnrichment

    with patch("security.services.enrich_software") as mocked_enrich:
        CveEnrichment().execute()

    mocked_enrich.assert_not_called()
    existing.refresh_from_db()
    assert existing.status == status
    assert existing.source == source


def test_enrichment_task_keeps_refreshing_auto_confirmed_matches(software):
    """
    A CpeMatch CONFIRMED automatically (by confidence threshold, never
    reviewed by a human) must still be passed to enrich_software() on every
    run, so its CVE reports keep refreshing over time. enrich_software()
    itself is responsible for not re-guessing the CPE while its own TTL is
    still valid — the task must not pre-filter it out entirely.
    """
    existing = CpeMatch.objects.create(
        software=software,
        cpe="cpe:2.3:a:openssl:openssl",
        cpe_rank=150,
        source=CpeMatch.SOURCE_AUTO,
        status=CpeMatch.STATUS_CONFIRMED,
    )

    from automation.tasks.cveEnrichment import CveEnrichment

    with patch("security.services.enrich_software") as mocked_enrich:
        CveEnrichment().execute()

    mocked_enrich.assert_called_once()
    assert mocked_enrich.call_args.args[0].id == software.id
    existing.refresh_from_db()
    assert existing.status == CpeMatch.STATUS_CONFIRMED
    assert existing.source == CpeMatch.SOURCE_AUTO


def test_enrichment_task_processes_pending_and_no_match_and_missing(db, software):
    other_software = SoftwareDictionary.objects.create(
        name="Firefox", publisher="Mozilla", version="100", installation_number=1
    )
    CpeMatch.objects.create(
        software=software,
        cpe="cpe:2.3:a:vendor:product:1.0:*:*:*:*:*:*:*",
        cpe_rank=10,
        source=CpeMatch.SOURCE_AUTO,
        status=CpeMatch.STATUS_PENDING_REVIEW,
    )
    # other_software has no CpeMatch at all yet.

    from automation.tasks.cveEnrichment import CveEnrichment

    with patch("security.services.enrich_software") as mocked_enrich:
        CveEnrichment().execute()

    processed_ids = {call.args[0].id for call in mocked_enrich.call_args_list}
    assert software.id in processed_ids
    assert other_software.id in processed_ids


def test_enrichment_task_returns_summary_with_counts(software):
    SoftwareDictionary.objects.create(
        name="Firefox", publisher="Mozilla", version="100", installation_number=1
    )

    def fake_enrich(sw):
        if sw.id == software.id:
            CpeMatch.objects.create(
                software=sw,
                cpe="cpe:2.3:a:openssl:openssl",
                cpe_rank=150,
                source=CpeMatch.SOURCE_AUTO,
                status=CpeMatch.STATUS_CONFIRMED,
            )
            CveReport.objects.create(software=sw, cve_id="CVE-2026-0001", cvss_score=9.0)
        else:
            CpeMatch.objects.create(
                software=sw,
                cpe="cpe:2.3:a:mozilla:firefox",
                cpe_rank=10,
                source=CpeMatch.SOURCE_AUTO,
                status=CpeMatch.STATUS_PENDING_REVIEW,
            )

    from automation.tasks.cveEnrichment import CveEnrichment

    with patch("security.services.enrich_software", side_effect=fake_enrich):
        summary = CveEnrichment().execute()

    assert summary is not None
    assert "2/2 software processed (0 failed)" in summary
    assert "1 CVE(s) found" in summary
    assert "1 reliable" in summary
    assert "1 to review" in summary
    assert "0 no match" in summary
    assert len(summary) <= 255


def test_enrichment_task_summary_counts_failures(db):
    software_a = SoftwareDictionary.objects.create(
        name="A", publisher="Vendor", version="1.0", installation_number=1
    )
    SoftwareDictionary.objects.create(
        name="B", publisher="Vendor", version="1.0", installation_number=1
    )

    from automation.tasks.cveEnrichment import CveEnrichment

    def fake_enrich(sw):
        if sw.id == software_a.id:
            raise RuntimeError("boom")

    with patch("security.services.enrich_software", side_effect=fake_enrich):
        summary = CveEnrichment().execute()

    assert "1/2 software processed (1 failed)" in summary


# --- Published date parsing -------------------------------------------------


def test_parse_published_date_handles_full_iso_timestamp():
    from datetime import date

    assert _parse_published_date("2026-08-28T17:45:35.161Z") == date(2026, 8, 28)


def test_parse_published_date_handles_bare_date():
    from datetime import date

    assert _parse_published_date("2022-01-01") == date(2022, 1, 1)


def test_parse_published_date_returns_none_for_missing_or_invalid():
    assert _parse_published_date(None) is None
    assert _parse_published_date("") is None
    assert _parse_published_date("not-a-date") is None


# --- Version-based CVE filtering --------------------------------------------


def test_installed_version_display_prefers_major_minor():
    software = SoftwareDictionary(major_version=1, minor_version=1, version="1.1.1k")
    assert installed_version_display(software) == "1.1"


def test_installed_version_display_falls_back_to_raw_version():
    software = SoftwareDictionary(major_version=None, minor_version=None, version="1.1.1k")
    assert installed_version_display(software) == "1.1.1k"


def test_parse_semver_accepts_dotted_numeric_only():
    assert _parse_semver("3.0.22") == (3, 0, 22)
    assert _parse_semver("1.1") == (1, 1)
    assert _parse_semver("abc") is None
    assert _parse_semver("1.1.1k") is None
    assert _parse_semver(None) is None


_OPENSSL_AFFECTED_RECORD = {
    "containers": {
        "cna": {
            "affected": [
                {
                    "versions": [
                        {"version": "4.0.0", "lessThan": "4.0.2", "status": "affected", "versionType": "semver"},
                        {"version": "3.6.0", "lessThan": "3.6.4", "status": "affected", "versionType": "semver"},
                        {"version": "3.0.0", "lessThan": "3.0.22", "status": "affected", "versionType": "semver"},
                    ]
                }
            ]
        }
    }
}


def test_cve_affects_version_inside_range():
    assert _cve_affects_version(_OPENSSL_AFFECTED_RECORD, "3.0.10") is True


def test_cve_affects_version_outside_all_ranges():
    # 1.1.1 predates every affected range (all start at 3.0.0+), so it's unaffected.
    assert _cve_affects_version(_OPENSSL_AFFECTED_RECORD, "1.1.1") is False


def test_cve_affects_version_at_upper_bound_is_excluded():
    assert _cve_affects_version(_OPENSSL_AFFECTED_RECORD, "3.0.22") is False


def test_cve_affects_version_lessthanorequal_includes_upper_bound():
    record = {
        "containers": {
            "cna": {
                "affected": [
                    {
                        "versions": [
                            {"version": "2.4.17", "lessThanOrEqual": "2.4.67", "status": "affected", "versionType": "semver"},
                        ]
                    }
                ]
            }
        }
    }
    assert _cve_affects_version(record, "2.4.67") is True
    assert _cve_affects_version(record, "2.4.68") is False


def test_cve_affects_version_kept_when_range_is_not_semver():
    record = {
        "containers": {
            "cna": {
                "affected": [
                    {
                        "versions": [
                            {"version": "abc123", "status": "affected", "versionType": "git"},
                        ]
                    }
                ]
            }
        }
    }
    # Can't compare a git commit range numerically, so the CVE is kept.
    assert _cve_affects_version(record, "3.0.10") is True


def test_cve_affects_version_kept_when_no_affected_data():
    assert _cve_affects_version({}, "3.0.10") is True


def test_cve_affects_version_kept_when_installed_version_unparseable():
    assert _cve_affects_version(_OPENSSL_AFFECTED_RECORD, "1.1.1k") is True


def test_cve_version_match_status_matched_vs_unknown():
    assert _cve_version_match_status(_OPENSSL_AFFECTED_RECORD, "3.0.10") == "matched"

    non_semver_record = {
        "containers": {
            "cna": {
                "affected": [
                    {"versions": [{"version": "abc123", "status": "affected", "versionType": "git"}]}
                ]
            }
        }
    }
    assert _cve_version_match_status(non_semver_record, "3.0.10") == "unknown"
    assert _cve_version_match_status({}, "3.0.10") == "unknown"
    assert _cve_version_match_status(_OPENSSL_AFFECTED_RECORD, "1.1.1k") == "unknown"


def test_cve_version_match_status_ignores_declared_versionType_when_value_is_numeric():
    """
    Real CVE records (e.g. Notepad++) report a plain numeric version with no
    versionType key at all, or with versionType="custom" even though the
    value is dotted-numeric. The comparison must go by whether the value
    itself parses, not by the declared versionType.
    """
    no_version_type = {
        "containers": {
            "cna": {"affected": [{"versions": [{"version": "8.9.3", "status": "affected"}]}]}
        }
    }
    assert _cve_version_match_status(no_version_type, "8.9.3") == "matched"
    assert _cve_version_match_status(no_version_type, "8.9.2") == "excluded"

    declared_custom_but_numeric = {
        "containers": {
            "cna": {
                "affected": [
                    {
                        "versions": [
                            {
                                "version": "0",
                                "lessThan": "8.9.4",
                                "status": "affected",
                                "versionType": "custom",
                            }
                        ]
                    }
                ]
            }
        }
    }
    assert _cve_version_match_status(declared_custom_but_numeric, "8.9.2") == "matched"
    assert _cve_version_match_status(declared_custom_but_numeric, "8.9.5") == "excluded"


def test_parse_vulnerability_lookup_response_filters_by_installed_version():
    payload = {
        "results": {
            "nvd": [
                [
                    "cve-2026-1",
                    {
                        "cveMetadata": {"cveId": "CVE-2026-1", "datePublished": "2026-01-01"},
                        "containers": {"cna": {**_OPENSSL_AFFECTED_RECORD["containers"]["cna"], "metrics": []}},
                    },
                ]
            ]
        },
        "total_count": 1,
        "page_size": 50,
        "page": 1,
    }

    kept = _parse_vulnerability_lookup_response(payload, installed_version="3.0.10")
    assert len(kept) == 1
    assert kept[0]["version_match"] == "matched"

    filtered_out = _parse_vulnerability_lookup_response(payload, installed_version="1.1.1")
    assert filtered_out == []

    unfiltered = _parse_vulnerability_lookup_response(payload, installed_version=None)
    assert len(unfiltered) == 1
    assert unfiltered[0]["version_match"] == "unknown"


def test_fetch_and_store_cves_persists_version_match_status(software, cve_config):
    with patch(
        "security.services.fetch_cves",
        return_value=[
            {"cve_id": "CVE-MATCHED", "cvss_score": 9.0, "published_date": None, "version_match": "matched"},
            {"cve_id": "CVE-UNKNOWN", "cvss_score": 5.0, "published_date": None, "version_match": "unknown"},
        ],
    ):
        fetch_and_store_cves(software, "cpe:2.3:a:openssl:openssl", config=cve_config)

    matches = dict(CveReport.objects.filter(software=software).values_list("cve_id", "version_match"))
    assert matches == {"CVE-MATCHED": "matched", "CVE-UNKNOWN": "unknown"}


# --- Stale CVE cleanup -------------------------------------------------------


def test_fetch_cves_returns_none_on_first_page_failure():
    class FailingResponse:
        status_code = 500
        text = "boom"

    with patch("security.services.requests.get", return_value=FailingResponse()):
        result = fetch_cves("http://vuln-lookup.example/api", "openssl", "openssl")

    assert result is None


def test_fetch_cves_returns_empty_list_on_success_with_no_results():
    class EmptyResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"results": {}, "total_count": 0, "page_size": 10, "page": 1}

    with patch("security.services.requests.get", return_value=EmptyResponse()):
        result = fetch_cves("http://vuln-lookup.example/api", "openssl", "openssl")

    assert result == []


def test_fetch_cves_stops_at_max_pages_for_very_popular_products():
    """
    A product with far more CVEs than MAX_FETCH_PAGES * page_size (e.g.
    Firefox: 6830+ CVEs at page_size=10) must not page forever — only the
    newest MAX_FETCH_PAGES pages are fetched (results are newest-first).
    """
    from security import services as security_services

    call_count = {"n": 0}

    class HugeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            call_count["n"] += 1
            return {
                "results": {
                    "nvd": [
                        [
                            f"cve-2026-{call_count['n']}",
                            {
                                "cveMetadata": {
                                    "cveId": f"CVE-2026-{call_count['n']}",
                                    "state": "PUBLISHED",
                                    "datePublished": "2026-01-01",
                                },
                                "containers": {"cna": {"metrics": []}},
                            },
                        ]
                    ]
                },
                "total_count": 100000,
                "page_size": 1,
                "page": call_count["n"],
            }

    with patch("security.services.requests.get", return_value=HugeResponse()):
        result = fetch_cves("http://vuln-lookup.example/api", "mozilla", "firefox")

    assert len(result) == security_services.MAX_FETCH_PAGES
    assert call_count["n"] == security_services.MAX_FETCH_PAGES


def _make_stale(cve_report):
    from datetime import timedelta

    from django.utils import timezone

    CveReport.objects.filter(pk=cve_report.pk).update(
        fetched_at=timezone.now() - timedelta(hours=48)
    )


def test_fetch_and_store_cves_removes_stale_reports_on_successful_refetch(software, cve_config):
    old = CveReport.objects.create(software=software, cve_id="CVE-OLD-0001", cvss_score=5.0)
    still_here = CveReport.objects.create(
        software=software, cve_id="CVE-STILL-HERE", cvss_score=6.0
    )
    _make_stale(old)
    _make_stale(still_here)

    with patch(
        "security.services.fetch_cves",
        return_value=[{"cve_id": "CVE-STILL-HERE", "cvss_score": 6.0, "published_date": None}],
    ):
        fetch_and_store_cves(software, "cpe:2.3:a:openssl:openssl", config=cve_config)

    remaining = set(CveReport.objects.filter(software=software).values_list("cve_id", flat=True))
    assert remaining == {"CVE-STILL-HERE"}


def test_fetch_and_store_cves_keeps_existing_reports_when_fetch_fails(software, cve_config):
    old = CveReport.objects.create(software=software, cve_id="CVE-OLD-0001", cvss_score=5.0)
    _make_stale(old)

    with patch("security.services.fetch_cves", return_value=None):
        fetch_and_store_cves(software, "cpe:2.3:a:openssl:openssl", config=cve_config)

    remaining = set(CveReport.objects.filter(software=software).values_list("cve_id", flat=True))
    assert remaining == {"CVE-OLD-0001"}


def test_fetch_and_store_cves_excludes_records_without_cvss_score(software, cve_config):
    with patch(
        "security.services.fetch_cves",
        return_value=[
            {"cve_id": "CVE-WITH-SCORE", "cvss_score": 7.5, "published_date": None},
            {"cve_id": "CVE-NO-SCORE", "cvss_score": None, "published_date": None},
        ],
    ):
        fetch_and_store_cves(software, "cpe:2.3:a:openssl:openssl", config=cve_config)

    remaining = set(CveReport.objects.filter(software=software).values_list("cve_id", flat=True))
    assert remaining == {"CVE-WITH-SCORE"}


def test_fetch_and_store_cves_removes_existing_report_that_lost_its_score(software, cve_config):
    """
    A CveReport already stored (from before this filter existed) with no
    CVSS score must be cleaned up on the next successful refetch, via the
    same stale-cleanup pass used for version/product mismatches.
    """
    no_score = CveReport.objects.create(software=software, cve_id="CVE-NO-SCORE", cvss_score=None)
    _make_stale(no_score)

    with patch("security.services.fetch_cves", return_value=[]):
        fetch_and_store_cves(software, "cpe:2.3:a:openssl:openssl", config=cve_config)

    assert CveReport.objects.filter(software=software).count() == 0


# --- Vulnerability-Lookup response parsing ---------------------------------


def test_parse_vulnerability_lookup_response_skips_rejected_cves():
    payload = {
        "results": {
            "nvd": [
                [
                    "cve-2026-40556",
                    {
                        "cveMetadata": {
                            "cveId": "CVE-2026-40556",
                            "state": "REJECTED",
                            "datePublished": "2026-04-29",
                        },
                        "containers": {"cna": {"rejectedReasons": []}},
                    },
                ],
                [
                    "cve-2026-1",
                    {
                        "cveMetadata": {
                            "cveId": "CVE-2026-1",
                            "state": "PUBLISHED",
                            "datePublished": "2026-01-01",
                        },
                        "containers": {"cna": {"metrics": []}},
                    },
                ],
            ]
        },
        "total_count": 2,
        "page_size": 50,
        "page": 1,
    }

    kept = _parse_vulnerability_lookup_response(payload)
    assert [record["cve_id"] for record in kept] == ["CVE-2026-1"]


def test_parse_vulnerability_lookup_response_dedupes_and_extracts_cvss():
    payload = {
        "results": {
            "nvd": [
                [
                    "cve-2021-1234",
                    {
                        "cveMetadata": {
                            "cveId": "CVE-2021-1234",
                            "datePublished": "2021-05-01T00:00:00",
                        },
                        "containers": {
                            "cna": {
                                "metrics": [
                                    {"cvssV3_1": {"baseScore": 9.8}},
                                ]
                            }
                        },
                    },
                ]
            ],
            "cvelistv5": [
                [
                    "cve-2021-1234",
                    {
                        "cveMetadata": {
                            "cveId": "CVE-2021-1234",
                            "datePublished": "2021-05-01T00:00:00",
                        },
                        "containers": {
                            "cna": {
                                "metrics": [
                                    {"cvssV2_0": {"baseScore": 7.5}},
                                ]
                            }
                        },
                    },
                ]
            ],
        },
        "total_count": 1,
        "page_size": 50,
        "page": 1,
    }

    records = _parse_vulnerability_lookup_response(payload)

    assert len(records) == 1
    assert records[0]["cve_id"] == "CVE-2021-1234"
    assert records[0]["cvss_score"] == 9.8
    from datetime import date

    assert records[0]["published_date"] == date(2021, 5, 1)


def test_parse_vulnerability_lookup_response_prefers_v3_over_v2_within_same_record():
    payload = {
        "results": {
            "nvd": [
                [
                    "cve-2022-0001",
                    {
                        "cveMetadata": {"cveId": "CVE-2022-0001", "datePublished": "2022-01-01"},
                        "containers": {
                            "cna": {
                                "metrics": [
                                    {"cvssV2_0": {"baseScore": 5.0}},
                                    {"cvssV3_0": {"baseScore": 6.5}},
                                ]
                            }
                        },
                    },
                ]
            ]
        },
        "total_count": 1,
        "page_size": 50,
        "page": 1,
    }

    records = _parse_vulnerability_lookup_response(payload)
    assert records[0]["cvss_score"] == 6.5


# --- CVE URL --------------------------------------------------------------


def test_build_cve_url_points_to_nvd():
    assert build_cve_url("CVE-2021-1234") == "https://nvd.nist.gov/vuln/detail/CVE-2021-1234"


def test_cve_report_serializer_shows_url_when_enabled(software):
    report = CveReport.objects.create(software=software, cve_id="CVE-2021-1234")
    data = CveReportSerializer(report, context={"show_cve_url": True}).data
    assert data["cve_url"] == "https://nvd.nist.gov/vuln/detail/CVE-2021-1234"


def test_cve_report_serializer_hides_url_when_disabled(software):
    report = CveReport.objects.create(software=software, cve_id="CVE-2021-1234")
    data = CveReportSerializer(report, context={"show_cve_url": False}).data
    assert data["cve_url"] is None


def test_cve_report_serializer_exposes_impacted_asset_count(software):
    software.installation_number = 42
    software.save()
    report = CveReport.objects.create(software=software, cve_id="CVE-2021-1234")
    data = CveReportSerializer(report, context={"show_cve_url": True}).data
    assert data["impacted_asset_count"] == 42


def test_cve_report_serializer_exposes_software_publisher_and_version(software):
    report = CveReport.objects.create(software=software, cve_id="CVE-2021-1234")
    data = CveReportSerializer(report, context={"show_cve_url": True}).data
    assert data["software_publisher"] == "OpenSSL Software Foundation"
    # major_version=1, minor_version=1 on the fixture -> "1.1", not the raw "1.1.1"
    assert data["software_version"] == "1.1"


def test_cve_report_serializer_software_version_falls_back_to_raw_version(db):
    software = SoftwareDictionary.objects.create(
        name="7-Zip", publisher="Igor Pavlov", version="19.00", installation_number=1
    )
    report = CveReport.objects.create(software=software, cve_id="CVE-2021-1234")
    data = CveReportSerializer(report, context={"show_cve_url": True}).data
    assert data["software_version"] == "19.00"


def test_cve_report_serializer_exposes_version_match(software):
    report = CveReport.objects.create(
        software=software, cve_id="CVE-2021-1234", version_match=CveReport.VERSION_MATCH_MATCHED
    )
    data = CveReportSerializer(report, context={"show_cve_url": True}).data
    assert data["version_match"] == "matched"


# --- CVE summary / dashboard tiles ------------------------------------------


def test_build_cve_summary_buckets_by_severity_and_counts_impacted_assets(software, asset):
    software.assets.add(asset)
    CveReport.objects.create(software=software, cve_id="CVE-2021-0001", cvss_score=9.8)
    CveReport.objects.create(software=software, cve_id="CVE-2021-0002", cvss_score=7.5)
    CveReport.objects.create(software=software, cve_id="CVE-2021-0003", cvss_score=5.0)
    CveReport.objects.create(software=software, cve_id="CVE-2021-0004", cvss_score=2.0)
    CveReport.objects.create(software=software, cve_id="CVE-2021-0005", cvss_score=None)

    summary = build_cve_summary(CveReport.objects.all())

    assert summary["total_cves"] == 5
    assert summary["vulnerable_software_count"] == 1
    assert summary["impacted_asset_count"] == 1
    assert summary["highest_cvss_score"] == 9.8
    assert summary["by_severity"] == {
        "critical": 1,
        "high": 1,
        "medium": 1,
        "low": 1,
        "unknown": 1,
    }


def test_build_cve_summary_empty_queryset():
    summary = build_cve_summary(CveReport.objects.none())

    assert summary["total_cves"] == 0
    assert summary["impacted_asset_count"] == 0
    assert summary["highest_cvss_score"] is None
    assert summary["by_severity"] == {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 0,
    }


# --- Config seeding ---------------------------------------------------------


def test_migration_seeds_cve_integration_config_readable_by_get_cve_config(db):
    from config.models import Config

    assert Config.objects.filter(name="cve_integration").exists()
    config = get_cve_config()
    assert config["min_confidence_rank"] == 100
    assert config["cache_validity_hours"] == 24
    assert config["show_cve_url"] is True
    assert config["vulnerability_lookup_url"] == ""
    assert config["cpe_guesser_url"] == ""


# --- Bulk review ------------------------------------------------------------


def _bulk_review(ids, decision):
    from django.contrib.auth.models import User
    from rest_framework.test import APIRequestFactory, force_authenticate

    from .views import CpeMatchViewSet

    user, _ = User.objects.get_or_create(
        username="test-reviewer", defaults={"is_superuser": True, "is_staff": True}
    )

    factory = APIRequestFactory()
    request = factory.post(
        "/security/cpe-matches/bulk-review/",
        {"ids": ids, "decision": decision},
        format="json",
    )
    force_authenticate(request, user=user)
    view = CpeMatchViewSet.as_view({"post": "bulk_review"})
    return view(request)


def test_bulk_review_confirms_several_matches_and_fetches_cves(software):
    other_software = SoftwareDictionary.objects.create(
        name="Firefox", publisher="Mozilla", version="100", installation_number=1
    )
    match_1 = CpeMatch.objects.create(
        software=software,
        cpe="cpe:2.3:a:openssl:openssl",
        cpe_rank=50,
        source=CpeMatch.SOURCE_AUTO,
        status=CpeMatch.STATUS_PENDING_REVIEW,
    )
    match_2 = CpeMatch.objects.create(
        software=other_software,
        cpe="cpe:2.3:a:mozilla:firefox",
        cpe_rank=50,
        source=CpeMatch.SOURCE_AUTO,
        status=CpeMatch.STATUS_PENDING_REVIEW,
    )

    with patch("security.views.fetch_and_store_cves") as mocked_fetch:
        response = _bulk_review([match_1.id, match_2.id], "confirm")

    assert response.status_code == 200
    assert response.data["missing_ids"] == []
    assert len(response.data["updated"]) == 2
    assert mocked_fetch.call_count == 2

    match_1.refresh_from_db()
    match_2.refresh_from_db()
    assert match_1.status == CpeMatch.STATUS_CONFIRMED
    assert match_2.status == CpeMatch.STATUS_CONFIRMED


def test_bulk_review_rejects_and_reports_missing_ids(software):
    match = CpeMatch.objects.create(
        software=software,
        cpe="cpe:2.3:a:openssl:openssl",
        cpe_rank=50,
        source=CpeMatch.SOURCE_AUTO,
        status=CpeMatch.STATUS_PENDING_REVIEW,
    )

    response = _bulk_review([match.id, 999999], "reject")

    assert response.status_code == 200
    assert response.data["missing_ids"] == [999999]
    match.refresh_from_db()
    assert match.status == CpeMatch.STATUS_REJECTED


def test_bulk_review_rejects_invalid_decision(software):
    match = CpeMatch.objects.create(
        software=software,
        cpe="cpe:2.3:a:openssl:openssl",
        cpe_rank=50,
        source=CpeMatch.SOURCE_AUTO,
        status=CpeMatch.STATUS_PENDING_REVIEW,
    )

    response = _bulk_review([match.id], "delete")

    assert response.status_code == 400
    match.refresh_from_db()
    assert match.status == CpeMatch.STATUS_PENDING_REVIEW


def test_bulk_review_rejects_empty_ids(db):
    response = _bulk_review([], "confirm")
    assert response.status_code == 400
