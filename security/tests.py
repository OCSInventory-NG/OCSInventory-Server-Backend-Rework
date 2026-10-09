import json
from datetime import timedelta
from pathlib import Path

import pytest
from automation.scheduler.models import Scheduler
from django.db import IntegrityError
from django.utils import timezone
from asset.inventory_base.models import InventoryBase
from inventory.software.models import AssetPlatform, SoftwareDictionary
from inventory.software_identity.models import SoftwareIdentity
from security.cvss import base_score, level
from security.kernel import is_kernel, is_running_kernel
from security.sources import nvd, osv
from security.models import (
    Finding,
    ProductCheck,
    Vulnerability,
)
from security import reading
from security.services import ScanService


@pytest.mark.django_db
class TestModels:
    def test_a_product_version_has_a_vulnerability_once(self):
        vulnerability = Vulnerability.objects.create(vuln_id="CVE-2026-13608")
        values = {
            "vulnerability": vulnerability,
            "scheme": "purl",
            "product": "pkg:deb/ubuntu/curl",
            "version": "8.5.0-2ubuntu10.13",
            "advisory_id": "UBUNTU-CVE-2026-13608",
        }
        Finding.objects.create(**values)

        with pytest.raises(IntegrityError):
            Finding.objects.create(**values)

    def test_a_product_is_checked_once_per_source(self):
        ProductCheck.objects.create(source="nvd", key="mozilla:firefox")
        ProductCheck.objects.create(source="osv", key="mozilla:firefox")

        with pytest.raises(IntegrityError):
            ProductCheck.objects.create(source="nvd", key="mozilla:firefox")


@pytest.mark.parametrize(
    "vector, expected",
    [
        # Scores of the real records the tests use, as their sources give them
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
        ("CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N", 7.4),
        ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N", 7.1),
        ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N", 5.5),
        # scope changed
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
        ("CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:L/I:L/A:N", 5.4),
        ("CVSS:3.0/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H", 8.8),
        ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
    ],
)
def test_cvss_base_score(vector, expected):
    assert base_score(vector) == expected


@pytest.mark.parametrize(
    "vector",
    [
        "",
        "CVSS:4.0/AV:L/AC:L/AT:N/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N",
        "AV:N/AC:L/Au:N/C:P/I:P/A:P",
        "CVSS:3.1/AV:N/AC:L",
    ],
)
def test_cvss_without_a_3x_base_score(vector):
    assert base_score(vector) is None


@pytest.mark.parametrize(
    "score, rating, expected",
    [
        (9.8, "", "critical"),
        (9.0, "low", "critical"),
        (7.0, "", "high"),
        (4.0, "", "medium"),
        (0.1, "", "low"),
        (0.0, "", "unknown"),
        (None, "medium", "medium"),
        (None, "Important", "high"),
        (None, "Moderate", "medium"),
        (None, "negligible", "low"),
        (None, "unimportant", "low"),
        (None, "not yet assigned", "unknown"),
        (None, "", "unknown"),
    ],
)
def test_level(score, rating, expected):
    assert level(score, rating) == expected


@pytest.mark.parametrize(
    "name, family, expected",
    [
        ("linux-image-6.8.0-87-generic", "deb", True),
        ("linux-modules-extra-6.8.0-87-generic:amd64", "deb", True),
        ("linux-headers-6.8.0-87-generic", "deb", True),
        ("linux-image-generic", "deb", True),
        ("linux-firmware", "deb", False),
        ("libc6:amd64", "deb", False),
        ("kernel-core", "rpm", True),
        ("kernel", "rpm", True),
        ("kernelshark", "rpm", False),
        ("linux-image-6.8.0-87-generic", "rpm", False),
    ],
)
def test_kernel_packages(name, family, expected):
    assert is_kernel(name, family) is expected


@pytest.mark.parametrize(
    "name, version, family, running, expected",
    [
        # the running kernel and its modules count
        ("linux-image-6.8.0-87-generic", "6.8.0-87.88", "deb", "6.8.0-87-generic", True),  # noqa: E501
        ("linux-modules-6.8.0-87-generic:amd64", "6.8.0-87.88", "deb", "6.8.0-87-generic", True),  # noqa: E501
        # an older kernel left installed, a meta package
        ("linux-image-6.8.0-85-generic", "6.8.0-85.85", "deb", "6.8.0-87-generic", False),  # noqa: E501
        ("linux-image-generic", "6.8.0.87.88", "deb", "6.8.0-87-generic", False),
        # a container runs the host kernel: no installed package is it
        ("linux-image-6.8.0-87-generic", "6.8.0-87.88", "deb", "6.17.2-1-pve", False),
        ("linux-image-6.8.0-87-generic", "6.8.0-87.88", "deb", "", False),
        ("kernel-core", "5.14.0-427.13.1.el9_4", "rpm", "5.14.0-427.13.1.el9_4.x86_64", True),  # noqa: E501
        ("kernel-core", "0:5.14.0-427.13.1.el9_4", "rpm", "5.14.0-427.13.1.el9_4.x86_64", True),  # noqa: E501
        ("kernel-core", "5.14.0-362.8.1.el9_3", "rpm", "5.14.0-427.13.1.el9_4.x86_64", False),  # noqa: E501
        ("kernel-core", "5.14.0-427.13.1.el9_4", "rpm", "6.17.2-1-pve", False),
    ],
)
def test_running_kernel(name, version, family, running, expected):
    assert is_running_kernel(name, version, family, running) is expected


# Real OSV records (2026-10-09), versions and references removed
OSV_RECORDS = json.loads(
    (Path(__file__).parent / "test_data" / "osv_records.json").read_text()
)


@pytest.mark.parametrize(
    "product, platform_key, expected",
    [
        ("pkg:deb/debian/curl", "debian:13", "Debian:13"),
        ("pkg:deb/ubuntu/curl", "ubuntu:24.04", "Ubuntu:24.04:LTS"),
        ("pkg:deb/ubuntu/curl", "ubuntu:20.04", "Ubuntu:20.04:LTS"),
        ("pkg:deb/ubuntu/curl", "ubuntu:23.10", "Ubuntu:23.10"),
        ("pkg:rpm/rocky/acl", "rocky:9", "Rocky Linux:9"),
        ("pkg:rpm/almalinux/acl", "almalinux:9", "AlmaLinux:9"),
        # a Red Hat package on AlmaLinux, an Ubuntu package on Debian
        ("pkg:rpm/redhat/acl", "almalinux:9", None),
        ("pkg:deb/ubuntu/curl", "debian:13", None),
        ("pkg:deb/debian/curl", "", None),
        ("mozilla:firefox", "windows", None),
    ],
)
def test_osv_ecosystem(product, platform_key, expected):
    assert osv.ecosystem(product, platform_key) == expected


def test_osv_package_name_is_the_purl_name_unquoted():
    assert osv.package_name("pkg:deb/debian/libstdc%2B%2B6") == "libstdc++6"
    assert osv.package_name("pkg:rpm/rocky/NetworkManager") == "NetworkManager"


def test_osv_query_follows_page_tokens():
    calls = []

    def post(url, payload):
        calls.append(payload)
        query = payload["queries"][0]
        if query.get("page_token") == "next":
            return {"results": [{"vulns": [{"id": "B", "modified": "2"}]}]}
        return {
            "results": [
                {"vulns": [{"id": "A", "modified": "1"}], "next_page_token": "next"},
                {},
            ]
        }

    client = osv.OsvClient(post=post, get=None, base_url="https://osv.test/v1")
    pairs = [("Debian:13", "curl", "8.14.1-2"), ("Debian:13", "zlib", "1:1.3")]

    result = client.query(pairs)

    assert result == {
        pairs[0]: [{"id": "A", "modified": "1"}, {"id": "B", "modified": "2"}],
        pairs[1]: [],
    }
    assert calls[0]["queries"][1] == {
        "package": {"name": "zlib", "ecosystem": "Debian:13"},
        "version": "1:1.3",
    }
    assert calls[1]["queries"][0]["page_token"] == "next"


def test_osv_debian_record():
    record = OSV_RECORDS["DEBIAN-CVE-2026-29167"]
    compact = osv.compact(record)

    assert osv.summary(record).startswith("Use After Free vulnerability")
    assert compact["vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert osv.findings(compact, "Debian:13", "apache2") == [
        {
            "cve": "CVE-2026-29167",
            "fixed_version": "2.4.68-1~deb13u1",
            "affected_range": "introduced 0, fixed 2.4.68-1~deb13u1",
            "rating": "not yet assigned",
        }
    ]


def test_osv_ubuntu_record():
    compact = osv.compact(OSV_RECORDS["UBUNTU-CVE-2026-13608"])

    assert compact["rating"] == "medium"
    [finding] = osv.findings(compact, "Ubuntu:24.04:LTS", "curl")
    assert (finding["cve"], finding["fixed_version"], finding["rating"]) == (
        "CVE-2026-13608",
        "8.5.0-2ubuntu10.15",
        "medium",
    )


def test_osv_rocky_advisory_gives_one_finding_per_cve():
    record = OSV_RECORDS["RLSA-2026:42736"]
    compact = osv.compact(record)

    found = osv.findings(compact, "Rocky Linux:9", "acl")

    assert [finding["cve"] for finding in found] == [
        "CVE-2026-54369",
        "CVE-2026-54370",
    ]
    assert {finding["fixed_version"] for finding in found} == {"0:2.4.0-1.el9_8"}
    assert {finding["rating"] for finding in found} == {"Important"}
    assert osv.summary(record) == "Important: acl security update"


def test_osv_advisory_without_cve_keeps_its_own_id():
    record = {
        "id": "DEBIAN-TEMP-0001",
        "modified": "2026-10-01T00:00:00Z",
        "affected": [
            {
                "package": {"name": "curl", "ecosystem": "Debian:13"},
                "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}]}],
            }
        ],
    }

    [finding] = osv.findings(osv.compact(record), "Debian:13", "curl")

    assert (finding["cve"], finding["fixed_version"]) == ("DEBIAN-TEMP-0001", "")
    assert finding["affected_range"] == "introduced 0"


# Real NVD CVE API answer for tunnelblick:tunnelblick (2026-10-09), trimmed
NVD_TUNNELBLICK = json.loads(
    (Path(__file__).parent / "test_data" / "nvd_tunnelblick.json").read_text()
)


def nvd_cve(*matches):
    """A compact NVD CVE holding the given cpeMatch bounds."""
    return {
        "id": "CVE-2026-0001",
        "matches": [
            {"criteria": criteria, **bounds} for criteria, bounds in matches
        ],
    }


class TestNvd:
    def test_compact_keeps_the_product_matches_and_the_primary_cvss(self):
        [cve] = [
            nvd.compact(item["cve"], "tunnelblick:tunnelblick")
            for item in NVD_TUNNELBLICK["vulnerabilities"]
        ]

        assert cve["id"] == "CVE-2026-31893"
        # NVD's own 3.1 score before the CNA's 4.0 one
        assert (cve["cvss_version"], cve["cvss_score"]) == ("3.1", 5.5)
        assert cve["cvss_vector"] == "CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
        assert cve["description"].startswith("Tunnelblick is an open source")
        assert len(cve["matches"]) == 6

    @pytest.mark.parametrize(
        "version, expected",
        [
            ("6.0", ("nvd_range", "8.0.1", "from 3.5.3 up to 8.0.1 excluded")),
            ("3.5.3", ("nvd_range", "8.0.1", "from 3.5.3 up to 8.0.1 excluded")),
            # exact versions that name a pre-release only match that one
            ("3.3", None),
            ("3.3beta26", ("nvd_range", "", "version 3.3 beta26")),
            ("9.0", None),
            ("9.0beta01", ("nvd_range", "", "version 9.0 beta01")),
            ("8.0.1", None),
            ("9.1 (build 6150)", None),
        ],
    )
    def test_evaluate_the_installed_version(self, version, expected):
        cve = nvd.compact(
            NVD_TUNNELBLICK["vulnerabilities"][0]["cve"], "tunnelblick:tunnelblick"
        )

        result = nvd.evaluate(cve, version)

        if expected is None:
            assert result is None
        else:
            assert (
                result["method"],
                result["fixed_version"],
                result["affected_range"],
            ) == expected
            assert result["uncertain"] is False

    def test_all_versions_is_uncertain_and_a_real_range_wins(self):
        everything = ("cpe:2.3:a:7-zip:7-zip:*:*:*:*:*:*:*:*", {})
        bounded = (
            "cpe:2.3:a:7-zip:7-zip:*:*:*:*:*:*:*:*",
            {"versionEndIncluding": "24.08"},
        )

        uncertain = nvd.evaluate(nvd_cve(everything), "24.08")
        definite = nvd.evaluate(nvd_cve(everything, bounded), "24.08")

        assert (uncertain["method"], uncertain["uncertain"]) == (
            "nvd_all_versions",
            True,
        )
        assert uncertain["affected_range"] == "all versions"
        # "up to ... included": no known fix
        assert (definite["method"], definite["fixed_version"]) == ("nvd_range", "")
        assert definite["affected_range"] == "up to 24.08 included"

    def test_matches_of_other_products_are_ignored_and_names_unescaped(self):
        cve = {
            "id": "CVE-2026-0002",
            "configurations": [
                {
                    "nodes": [
                        {
                            "cpeMatch": [
                                {
                                    "vulnerable": True,
                                    "criteria": "cpe:2.3:a:notepad-plus-plus:"
                                    "notepad\\+\\+:8.9.8:*:*:*:*:*:*:*",
                                },
                                {
                                    "vulnerable": True,
                                    "criteria": "cpe:2.3:a:other:product"
                                    ":*:*:*:*:*:*:*:*",
                                },
                                {
                                    "vulnerable": False,
                                    "criteria": "cpe:2.3:o:microsoft:windows"
                                    ":-:*:*:*:*:*:*:*",
                                },
                            ]
                        }
                    ]
                }
            ],
        }

        compact = nvd.compact(cve, "notepad-plus-plus:notepad++")

        assert len(compact["matches"]) == 1
        assert nvd.evaluate(compact, "8.9.8")["affected_range"] == "version 8.9.8"

    def test_client_pages_and_spaces_its_requests(self):
        pages = [
            {"resultsPerPage": 1, "startIndex": 0, "totalResults": 2,
             "vulnerabilities": NVD_TUNNELBLICK["vulnerabilities"]},
            {"resultsPerPage": 1, "startIndex": 1, "totalResults": 2,
             "vulnerabilities": NVD_TUNNELBLICK["vulnerabilities"]},
        ]
        calls, sleeps = [], []

        def get(url, params, headers):
            calls.append((params, headers))
            return pages[len(calls) - 1]

        client = nvd.NvdClient(
            get=get, sleep=sleeps.append, api_key="", base_url="https://nvd.test"
        )

        cves = client.product_cves("tunnelblick:tunnelblick")

        assert len(cves) == 2
        assert [params["startIndex"] for params, _ in calls] == [0, 1]
        assert calls[0][0]["virtualMatchString"].startswith(
            "cpe:2.3:a:tunnelblick:tunnelblick:"
        )
        # no wait before the first request, 6.5 s without a key after it
        assert sleeps == [6.5]
        assert calls[0][1] == {}

    def test_an_api_key_is_sent_and_shortens_the_spacing(self):
        sleeps, headers_seen = [], []

        def get(url, params, headers):
            headers_seen.append(headers)
            return {"resultsPerPage": 0, "totalResults": 0, "vulnerabilities": []}

        client = nvd.NvdClient(
            get=get, sleep=sleeps.append, api_key="secret", base_url="https://nvd.test"
        )
        client.product_cves("a:b")
        client.product_cves("c:d")

        assert headers_seen == [{"apiKey": "secret"}, {"apiKey": "secret"}]
        assert sleeps == [0.7]

    def test_rate_limit_answers_raise(self):
        def get(url, params, headers):
            raise nvd.RateLimited("403")

        client = nvd.NvdClient(
            get=get, sleep=lambda _: None, base_url="https://nvd.test"
        )

        with pytest.raises(nvd.RateLimited):
            client.product_cves("a:b")


def identify(
    name, version, family, key, scheme, product, status="matched", reason=""
):
    """A dictionary entry and its identity."""
    entry = SoftwareDictionary.objects.create(
        name=name,
        version=version,
        platform_family=family,
        platform_key=key,
        installation_number=1,
    )
    SoftwareIdentity.objects.create(
        entry=entry,
        family=family,
        match_key=name.lower(),
        status=status,
        reason=reason,
        scheme=scheme,
        product=product,
        version=version,
    )
    return entry


class FakeOsv:
    """OSV answering from the real records of the tests."""

    def __init__(self, vulns, records=OSV_RECORDS, failing=()):
        self.vulns = vulns
        self.records = records
        self.failing = set(failing)
        self.queried, self.fetched = [], []

    def query(self, pairs):
        self.queried += pairs
        return {pair: self.vulns.get(pair, []) for pair in pairs}

    def advisory(self, advisory_id):
        self.fetched.append(advisory_id)
        if advisory_id in self.failing:
            raise OSError("connection reset")
        return self.records[advisory_id]


class FakeNvd:
    def __init__(self, cves=None, rate_limited=()):
        self.cves = cves or {}
        self.rate_limited = set(rate_limited)
        self.asked = []

    def product_cves(self, product):
        self.asked.append(product)
        if product in self.rate_limited:
            raise nvd.RateLimited("NVD answered 403")
        return self.cves.get(product, [])


CURL = ("Ubuntu:24.04:LTS", "curl", "8.5.0-2ubuntu10.13")
CURL_VULNS = {CURL: [{"id": "UBUNTU-CVE-2026-13608", "modified": "1"}]}
TUNNELBLICK_CVES = [
    nvd.compact(item["cve"], "tunnelblick:tunnelblick")
    for item in NVD_TUNNELBLICK["vulnerabilities"]
]


def curl_identity():
    return identify(
        "curl", "8.5.0-2ubuntu10.13", "deb", "ubuntu:24.04", "purl",
        "pkg:deb/ubuntu/curl",
    )


@pytest.mark.django_db
class TestScan:
    def test_osv_findings_with_their_details(self):
        curl_identity()

        counts = ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())

        finding = Finding.objects.get()
        assert (finding.scheme, finding.product, finding.version) == (
            "purl",
            "pkg:deb/ubuntu/curl",
            "8.5.0-2ubuntu10.13",
        )
        assert finding.fixed_version == "8.5.0-2ubuntu10.15"
        assert finding.advisory_id == "UBUNTU-CVE-2026-13608"
        vulnerability = finding.vulnerability
        assert vulnerability.vuln_id == "CVE-2026-13608"
        assert (vulnerability.cvss_version, vulnerability.cvss_score) == ("3.1", 7.4)
        assert vulnerability.distro_rating == "medium"
        assert vulnerability.url == (
            "https://osv.dev/vulnerability/UBUNTU-CVE-2026-13608"
        )
        assert vulnerability.summary.startswith("A flaw in the libcurl")
        check = ProductCheck.objects.get(source="osv")
        assert check.key == "Ubuntu:24.04:LTS|curl|8.5.0-2ubuntu10.13"
        assert check.checked_at is not None and check.error == ""
        assert counts["osv_checked"] == 1

    def test_a_rocky_advisory_gives_one_finding_per_cve(self):
        identify(
            "acl", "2.3.1-4.el9", "rpm", "rocky:9", "purl", "pkg:rpm/rocky/acl"
        )
        pair = ("Rocky Linux:9", "acl", "2.3.1-4.el9")

        ScanService.refresh(
            FakeOsv({pair: [{"id": "RLSA-2026:42736", "modified": "1"}]}), FakeNvd()
        )

        found = Finding.objects.values_list("vulnerability__vuln_id", flat=True)
        assert sorted(found) == ["CVE-2026-54369", "CVE-2026-54370"]
        assert set(Vulnerability.objects.values_list("distro_rating", flat=True)) == {
            "Important"
        }

    def test_uncovered_packages_are_not_queried(self):
        identify(
            "docker-ce", "5:29.8.0-1", "deb", "ubuntu:22.04", "", "",
            status="unsupported", reason="third_party",
        )
        identify(
            "openssl", "1:3.0.7-27.el9", "rpm", "almalinux:9", "purl",
            "pkg:rpm/redhat/openssl",
        )
        osv_client = FakeOsv({})

        ScanService.refresh(osv_client, FakeNvd())

        assert osv_client.queried == []

    def test_fresh_checks_and_unchanged_advisories_are_not_asked_again(self):
        curl_identity()
        ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())
        again = FakeOsv(CURL_VULNS)

        ScanService.refresh(again, FakeNvd())
        assert again.queried == []

        ProductCheck.objects.update(checked_at=timezone.now() - timedelta(hours=25))
        stale = FakeOsv(CURL_VULNS)
        ScanService.refresh(stale, FakeNvd())
        assert stale.queried == [CURL]
        # same "modified": the cached advisory is used
        assert stale.fetched == []
        # the pair remembers the advisories it was built from
        assert ProductCheck.objects.get().payload == {"UBUNTU-CVE-2026-13608": "1"}

    def test_a_failing_advisory_keeps_the_previous_findings(self):
        curl_identity()
        ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())
        ProductCheck.objects.update(checked_at=timezone.now() - timedelta(hours=25))
        changed = {CURL: [{"id": "UBUNTU-CVE-2026-13608", "modified": "2"}]}

        counts = ScanService.refresh(
            FakeOsv(changed, failing={"UBUNTU-CVE-2026-13608"}), FakeNvd()
        )

        assert Finding.objects.count() == 1
        assert "UBUNTU-CVE-2026-13608" in ProductCheck.objects.get().error
        assert counts["osv_failed"] == 1

    def test_a_failing_batch_is_recorded_on_its_pairs(self):
        curl_identity()

        class Down(FakeOsv):
            def query(self, pairs):
                raise OSError("OSV unreachable")

        counts = ScanService.refresh(Down({}), FakeNvd())

        check = ProductCheck.objects.get()
        assert check.checked_at is None and "OSV unreachable" in check.error
        assert counts["osv_failed"] == 1

    def test_nvd_findings_per_installed_version(self):
        identify(
            "Tunnelblick", "6.0", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        identify(
            "Tunnelblick", "8.0.1", "macos", "macos", "cpe", "tunnelblick:tunnelblick",
            status="validated",
        )

        ScanService.refresh(
            FakeOsv({}), FakeNvd({"tunnelblick:tunnelblick": TUNNELBLICK_CVES})
        )

        finding = Finding.objects.get()
        assert (finding.version, finding.fixed_version, finding.method) == (
            "6.0",
            "8.0.1",
            "nvd_range",
        )
        vulnerability = finding.vulnerability
        assert (vulnerability.source, vulnerability.cvss_score) == ("nvd", 5.5)
        assert vulnerability.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-31893"
        product_check = ProductCheck.objects.get(key="tunnelblick:tunnelblick")
        assert product_check.payload == TUNNELBLICK_CVES
        assert ProductCheck.objects.filter(key="tunnelblick:tunnelblick|6.0").exists()

    def test_a_new_version_uses_the_cached_product(self):
        identify(
            "Tunnelblick", "8.0.1", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        ScanService.refresh(
            FakeOsv({}), FakeNvd({"tunnelblick:tunnelblick": TUNNELBLICK_CVES})
        )
        identify(
            "Tunnelblick", "3.5.3", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        nvd_client = FakeNvd()

        ScanService.refresh(FakeOsv({}), nvd_client)

        assert nvd_client.asked == []
        assert list(Finding.objects.values_list("version", flat=True)) == ["3.5.3"]

    def test_a_rate_limit_stops_the_nvd_part(self):
        identify("A", "1.0", "windows", "windows", "cpe", "a:a")
        identify("B", "1.0", "windows", "windows", "cpe", "b:b")
        nvd_client = FakeNvd(rate_limited={"a:a"})

        counts = ScanService.refresh(FakeOsv({}), nvd_client)

        assert nvd_client.asked == ["a:a"]
        assert "403" in ProductCheck.objects.get(key="a:a").error
        assert counts["nvd_rate_limited"] == 1

    def test_findings_of_versions_no_longer_installed_are_removed(self):
        entry = curl_identity()
        ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())
        entry.delete()

        ScanService.refresh(FakeOsv({}), FakeNvd())

        assert not Finding.objects.exists()
        assert not Vulnerability.objects.exists()

    def test_the_scan_task_is_seeded_inactive(self):
        task = Scheduler.objects.get(name="vulnerabilityScan.VulnerabilityScan")

        assert (task.recurrence, task.active) == ("hourly", False)


def machine(name, family="", running=""):
    asset = InventoryBase.objects.create(
        name=name,
        description="desc",
        serial=f"SER-{name}",
        osname="Linux",
        osversion="1",
        uuid=f"uuid-{name}",
        domain="example",
        agent="agent",
    )
    AssetPlatform.objects.create(asset=asset, family=family, running_kernel=running)
    return asset


def vulnerability(vuln_id, score=None, rating="", source="osv"):
    return Vulnerability.objects.create(
        vuln_id=vuln_id,
        summary=f"summary of {vuln_id}",
        cvss_score=score,
        cvss_version="3.1" if score else "",
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" if score else "",
        distro_rating=rating,
        source=source,
        url=f"https://example.test/{vuln_id}",
    )


def affect(entry, vuln, fixed="", method="osv", uncertain=False, advisory=""):
    identity = entry.identity
    return Finding.objects.create(
        vulnerability=vuln,
        scheme=identity.scheme,
        product=identity.product,
        version=identity.version,
        advisory_id=advisory or vuln.vuln_id,
        fixed_version=fixed,
        affected_range=f"fixed {fixed}" if fixed else "introduced 0",
        method=method,
        uncertain=uncertain,
    )


def checked(source, key, error="", at=None):
    return ProductCheck.objects.create(
        source=source,
        key=key,
        checked_at=None if error else (at or timezone.now()),
        error=error,
    )


@pytest.fixture
def fleet(db):
    """Two Ubuntu machines, a container, a Mac, and their identified software."""
    ubuntu = machine("ubuntu", "deb", "6.8.0-87-generic")
    other = machine("other", "deb", "6.8.0-90-generic")
    container = machine("container", "deb", "6.17.2-1-pve")
    mac = machine("mac", "macos")
    curl = curl_identity()
    curl.assets.add(ubuntu, other, container)
    kernel = identify(
        "linux-image-6.8.0-87-generic", "6.8.0-87.88", "deb", "ubuntu:24.04",
        "purl", "pkg:deb/ubuntu/linux",
    )
    kernel.assets.add(ubuntu, other, container)
    docker = identify(
        "docker-ce", "5:29.8.0-1", "deb", "ubuntu:24.04", "", "",
        status="unsupported", reason="third_party",
    )
    docker.assets.add(ubuntu)
    tunnelblick = identify(
        "Tunnelblick", "6.0", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
    )
    tunnelblick.assets.add(mac)
    review = identify(
        "GitHub Desktop", "3.4", "macos", "macos", "", "", status="review"
    )
    review.assets.add(mac)
    curl_vuln = vulnerability("CVE-2026-13608", score=7.4, rating="medium")
    affect(
        curl, curl_vuln, fixed="8.5.0-2ubuntu10.15", advisory="UBUNTU-CVE-2026-13608"
    )
    kernel_vuln = vulnerability("CVE-2026-0100", score=9.8)
    affect(kernel, kernel_vuln, fixed="6.8.0-90.91")
    mac_vuln = vulnerability("CVE-2026-31893", score=5.5, source="nvd")
    affect(tunnelblick, mac_vuln, fixed="8.0.1", method="nvd_range")
    seven_zip = vulnerability("CVE-2026-0200", rating="low", source="nvd")
    affect(tunnelblick, seven_zip, method="nvd_all_versions", uncertain=True)
    checked("osv", "Ubuntu:24.04:LTS|curl|8.5.0-2ubuntu10.13")
    checked("osv", "Ubuntu:24.04:LTS|linux|6.8.0-87.88")
    checked("nvd", "tunnelblick:tunnelblick")
    checked("nvd", "tunnelblick:tunnelblick|6.0")
    return {
        "ubuntu": ubuntu, "other": other, "container": container, "mac": mac,
        "curl": curl, "kernel": kernel, "tunnelblick": tunnelblick,
    }


def rows_by_id(response):
    return {row["vuln_id"]: row for row in response.data}


@pytest.mark.django_db
class TestVulnerabilityApi:
    def test_list_groups_by_vulnerability_and_counts_machines(self, api_client, fleet):
        response = api_client.get("/vulnerabilities/")

        assert response.status_code == 200
        # highest score first, unknown scores last
        assert [row["vuln_id"] for row in response.data] == [
            "CVE-2026-0100",
            "CVE-2026-13608",
            "CVE-2026-31893",
            "CVE-2026-0200",
        ]
        curl = rows_by_id(response)["CVE-2026-13608"]
        assert (curl["machines"], curl["fix_available"], curl["level"]) == (
            3,
            True,
            "high",
        )
        assert curl["products"] == [
            {"product": "pkg:deb/ubuntu/curl", "version": "8.5.0-2ubuntu10.13"}
        ]
        assert curl["product_count"] == 1
        assert curl["fixed_versions"] == ["8.5.0-2ubuntu10.15"]
        assert rows_by_id(response)["CVE-2026-0200"]["fixed_versions"] == []
        uncertain = rows_by_id(response)["CVE-2026-0200"]
        assert (uncertain["uncertain"], uncertain["level"]) == (True, "low")

    def test_only_the_running_kernel_counts(self, api_client, fleet):
        response = api_client.get("/vulnerabilities/")

        # installed on three machines, running on one: not on the newer
        # kernel machine, not on the container (host kernel)
        assert rows_by_id(response)["CVE-2026-0100"]["machines"] == 1

    def test_findings_of_uncovered_products_are_not_shown(self, api_client, fleet):
        docker = SoftwareDictionary.objects.get(name="docker-ce")
        Finding.objects.create(
            vulnerability=vulnerability("CVE-2026-0300", score=8.0),
            scheme="purl",
            product="pkg:deb/docker/docker-ce",
            version=docker.version,
            advisory_id="CVE-2026-0300",
        )

        response = api_client.get("/vulnerabilities/")

        assert "CVE-2026-0300" not in rows_by_id(response)

    @pytest.mark.parametrize(
        "query, expected",
        [
            ("level=critical", ["CVE-2026-0100"]),
            ("level=low", ["CVE-2026-0200"]),
            ("fix=no", ["CVE-2026-0200"]),
            ("family=macos", ["CVE-2026-31893", "CVE-2026-0200"]),
            ("search=curl", ["CVE-2026-13608"]),
            ("search=cve-2026-3189", ["CVE-2026-31893"]),
            ("ordering=-machines", ["CVE-2026-13608", "CVE-2026-0100",
                                    "CVE-2026-31893", "CVE-2026-0200"]),
        ],
    )
    def test_filters(self, api_client, fleet, query, expected):
        response = api_client.get(f"/vulnerabilities/?{query}")

        assert [row["vuln_id"] for row in response.data] == expected

    def test_machine_filter(self, api_client, fleet):
        other = api_client.get(f"/vulnerabilities/?asset={fleet['other'].id}")
        ubuntu = api_client.get(f"/vulnerabilities/?asset={fleet['ubuntu'].id}")

        assert [row["vuln_id"] for row in other.data] == ["CVE-2026-13608"]
        assert [row["vuln_id"] for row in ubuntu.data] == [
            "CVE-2026-0100",
            "CVE-2026-13608",
        ]
        assert rows_by_id(ubuntu)["CVE-2026-13608"]["machines"] == 1

    @pytest.mark.parametrize(
        "query", ["level=urgent", "fix=maybe", "asset=x", "ordering=name"]
    )
    def test_invalid_filters_are_refused(self, api_client, fleet, query):
        assert api_client.get(f"/vulnerabilities/?{query}").status_code == 400

    def test_pagination(self, api_client, fleet):
        response = api_client.get("/vulnerabilities/?limit=2&offset=1")

        assert response.data["count"] == 4
        assert [row["vuln_id"] for row in response.data["results"]] == [
            "CVE-2026-13608",
            "CVE-2026-31893",
        ]

    def test_detail(self, api_client, fleet):
        response = api_client.get("/vulnerabilities/CVE-2026-13608/")

        assert response.status_code == 200
        assert response.data["vuln_id"] == "CVE-2026-13608"
        assert response.data["cvss_vector"].startswith("CVSS:3.1/")
        [finding] = response.data["findings"]
        assert finding["advisory_id"] == "UBUNTU-CVE-2026-13608"
        assert finding["advisory_url"] == (
            "https://osv.dev/vulnerability/UBUNTU-CVE-2026-13608"
        )
        assert finding["fixed_version"] == "8.5.0-2ubuntu10.15"
        assert finding["identity_status"] == "matched"
        assert sorted(m["name"] for m in finding["machines"]) == [
            "container",
            "other",
            "ubuntu",
        ]

    def test_detail_of_an_nvd_vulnerability_links_to_the_nvd(self, api_client, fleet):
        response = api_client.get("/vulnerabilities/CVE-2026-31893/")

        [finding] = response.data["findings"]
        assert finding["advisory_url"] == (
            "https://nvd.nist.gov/vuln/detail/CVE-2026-31893"
        )
        assert [m["name"] for m in finding["machines"]] == ["mac"]

    def test_unknown_vulnerability(self, api_client, fleet):
        assert api_client.get("/vulnerabilities/CVE-1999-0001/").status_code == 404

    def test_fleet_coverage(self, api_client, fleet):
        identify(
            "acl", "2.3.1-4.el9", "rpm", "rocky:9", "purl", "pkg:rpm/rocky/acl"
        ).assets.add(machine("rocky", "rpm", "6.17.2-1-pve"))
        failed = identify(
            "zlib", "1:1.3", "deb", "ubuntu:24.04", "purl", "pkg:deb/ubuntu/zlib"
        )
        failed.assets.add(fleet["ubuntu"])
        checked("osv", "Ubuntu:24.04:LTS|zlib|1:1.3", error="OSV unreachable")
        identify(
            "openssl", "1:3.0.7", "rpm", "almalinux:9", "purl",
            "pkg:rpm/redhat/openssl",
        ).assets.add(fleet["ubuntu"])

        response = api_client.get("/vulnerabilities/coverage/")

        assert response.status_code == 200
        families = {row["family"]: row for row in response.data["families"]}
        assert families["deb"]["entries"] == {
            "checked": 2,
            "check_failed": 1,
            "third_party": 1,
        }
        # the kernel entry is checked, but running on one machine of three
        assert families["deb"]["installations"] == {
            "checked": 4,
            "kernel_not_running": 2,
            "check_failed": 1,
            "third_party": 1,
        }
        assert families["rpm"]["entries"] == {"pending": 1, "not_handled": 1}
        assert families["macos"]["entries"] == {"checked": 1, "no_identity": 1}
        assert response.data["kernels"] == {
            "checked": 1,
            "host_or_custom": 3,
        }
        assert response.data["last_check"] is not None

    def test_machine_coverage(self, api_client, fleet):
        response = api_client.get(
            f"/vulnerabilities/coverage/?asset={fleet['container'].id}"
        )

        assert response.data["kernel"] == "host_or_custom"
        assert response.data["unchecked"] == 1
        assert response.data["families"][0]["installations"] == {
            "checked": 1,
            "kernel_not_running": 1,
        }

    def test_permissions(self, make_api_client, fleet):
        viewer = make_api_client("view_vulnerability")
        nobody = make_api_client(username="nobody")

        assert viewer.get("/vulnerabilities/").status_code == 200
        assert viewer.get("/vulnerabilities/coverage/").status_code == 200
        assert nobody.get("/vulnerabilities/").status_code == 403


@pytest.mark.parametrize(
    "product, expected",
    [
        ("pkg:deb/debian/curl", "curl"),
        # signed kernel images are published under the kernel source
        ("pkg:deb/debian/linux-signed-amd64", "linux"),
        ("pkg:deb/ubuntu/linux-signed", "linux"),
        ("pkg:deb/ubuntu/linux-signed-hwe-6.8", "linux-hwe-6.8"),
        ("pkg:rpm/rocky/kernel", "kernel"),
    ],
)
def test_osv_query_name(product, expected):
    assert osv.query_name(product) == expected


@pytest.mark.parametrize(
    "name, family, source, expected",
    [
        # built from the kernel source but not the kernel itself
        ("linux-libc-dev:amd64", "deb", "linux", True),
        ("linux-tools-6.8.0-85-generic", "deb", "linux-hwe-6.8", True),
        ("linux-image-6.12.48+deb13-amd64", "deb", "linux-signed-amd64", True),
        ("perf", "rpm", "kernel", True),
        ("bpftool", "rpm", "kernel", True),
        ("curl", "deb", "curl", False),
        ("linux-firmware", "deb", "linux-firmware", False),
    ],
)
def test_kernel_packages_by_source(name, family, source, expected):
    assert is_kernel(name, family, source) is expected


@pytest.mark.parametrize(
    "name, version, family, source",
    [
        ("linux-libc-dev:amd64", "6.8.0-87.88", "deb", "linux"),
        ("linux-tools-common", "6.8.0-87.88", "deb", "linux"),
        ("perf", "5.14.0-427.13.1.el9_4", "rpm", "kernel"),
    ],
)
def test_kernel_source_packages_are_never_the_running_kernel(
    name, version, family, source
):
    running = "6.8.0-87-generic" if family == "deb" else "5.14.0-427.13.1.el9_4.x86_64"

    assert not is_running_kernel(name, version, family, running, source)


@pytest.mark.django_db
class TestReviewFixes:
    def test_a_pair_that_comes_back_is_queried_again(self):
        entry = curl_identity()
        ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())
        entry.delete()
        ScanService.refresh(FakeOsv({}), FakeNvd())
        curl_identity()
        osv_client = FakeOsv(CURL_VULNS)

        ScanService.refresh(osv_client, FakeNvd())

        assert osv_client.queried == [CURL]
        assert Finding.objects.count() == 1

    def test_a_new_version_of_a_checked_product_is_pending(self):
        identify(
            "Tunnelblick", "8.0.1", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        ScanService.refresh(
            FakeOsv({}), FakeNvd({"tunnelblick:tunnelblick": TUNNELBLICK_CVES})
        )
        identify(
            "Tunnelblick", "6.0", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )

        families = {row["family"]: row for row in reading.coverage()["families"]}

        assert families["macos"]["entries"] == {"checked": 1, "pending": 1}

    def test_a_rate_limit_still_evaluates_cached_products(self):
        identify(
            "Tunnelblick", "8.0.1", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        ScanService.refresh(
            FakeOsv({}), FakeNvd({"tunnelblick:tunnelblick": TUNNELBLICK_CVES})
        )
        identify(
            "Tunnelblick", "6.0", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        identify("A", "1.0", "windows", "windows", "cpe", "a:a")

        ScanService.refresh(FakeOsv({}), FakeNvd(rate_limited={"a:a"}))

        assert list(Finding.objects.values_list("version", flat=True)) == ["6.0"]

    def test_signed_kernel_images_are_queried_under_the_kernel_source(self):
        identify(
            "linux-image-6.12.48+deb13-amd64", "6.12.48-1", "deb", "debian:13",
            "purl", "pkg:deb/debian/linux-signed-amd64",
        )
        osv_client = FakeOsv({})

        ScanService.refresh(osv_client, FakeNvd())

        assert osv_client.queried == [("Debian:13", "linux", "6.12.48-1")]

    def test_kernel_source_packages_do_not_count_in_a_container(self):
        container = machine("container", "deb", "6.17.2-1-pve")
        libc = identify(
            "linux-libc-dev:amd64", "6.8.0-87.88", "deb", "ubuntu:24.04", "purl",
            "pkg:deb/ubuntu/linux",
        )
        libc.assets.add(container)
        affect(libc, vulnerability("CVE-2026-0100", score=9.8))

        rows = reading.vulnerability_rows(asset_id=container.id)
        status = reading.coverage(container.id)

        assert rows == []
        assert status["kernel"] == "host_or_custom"

    def test_short_osv_answers_fail_the_missing_pairs(self):
        curl_identity()

        class Short(FakeOsv):
            def query(self, pairs):
                self.queried += pairs
                return {}

        counts = ScanService.refresh(Short({}), FakeNvd())

        assert ProductCheck.objects.get().error != ""
        assert counts["osv_failed"] == 1

    def test_unicode_digits_are_not_a_machine_id(self, api_client):
        assert api_client.get("/vulnerabilities/?asset=\u00b2").status_code == 400


def test_nvd_criteria_split_on_unescaped_colons_only():
    cve = {
        "id": "CVE-2026-0003",
        "configurations": [
            {
                "nodes": [
                    {
                        "cpeMatch": [
                            {
                                "vulnerable": True,
                                "criteria": "cpe:2.3:a:acme:foo\\:bar:2.0:*:*:*:*:*:*:*",  # noqa: E501
                            }
                        ]
                    }
                ]
            }
        ],
    }

    compact = nvd.compact(cve, "acme:foo:bar")

    assert nvd.evaluate(compact, "2.0")["affected_range"] == "version 2.0"


@pytest.mark.django_db
class TestScanProgressAndSpeed:
    def test_progress_is_reported_per_batch_and_per_product(self):
        curl_identity()
        identify(
            "Tunnelblick", "6.0", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        messages = []

        ScanService.refresh(
            FakeOsv(CURL_VULNS),
            FakeNvd({"tunnelblick:tunnelblick": TUNNELBLICK_CVES}),
            progress=messages.append,
        )

        assert any(m.startswith("OSV batch 1/1") for m in messages)
        assert any("1 advisories fetched" in m for m in messages)
        assert any(
            m.startswith("NVD product 1/1") and "tunnelblick:tunnelblick" in m
            for m in messages
        )

    def test_advisories_are_fetched_in_parallel(self):
        import threading

        ids = ["DEBIAN-CVE-2026-29167", "UBUNTU-CVE-2026-13608", "RLSA-2026:42736"]
        identify(
            "acl", "2.3.1-4.el9", "rpm", "rocky:9", "purl", "pkg:rpm/rocky/acl"
        )
        pair = ("Rocky Linux:9", "acl", "2.3.1-4.el9")
        # answers only when the three advisories are asked at the same time
        together = threading.Barrier(3, timeout=5)

        class Parallel(FakeOsv):
            def advisory(self, advisory_id):
                together.wait()
                return super().advisory(advisory_id)

        vulns = {pair: [{"id": advisory_id, "modified": "1"} for advisory_id in ids]}
        counts = ScanService.refresh(Parallel(vulns), FakeNvd())

        assert counts.get("osv_failed", 0) == 0
        assert Finding.objects.count() == 4


@pytest.mark.django_db
def test_full_advisories_are_not_kept_while_a_batch_downloads():
    """Kernel records are 350 to 700 KB of JSON: a batch must not hold them all."""
    import threading
    import weakref

    from security import services

    class Record(dict):
        """A dict that can be watched while alive."""

    alive, peak, lock = [0], [0], threading.Lock()

    def released():
        with lock:
            alive[0] -= 1

    curl = OSV_RECORDS["UBUNTU-CVE-2026-13608"]

    class Watched(FakeOsv):
        def advisory(self, advisory_id):
            record = Record(curl, id=advisory_id)
            with lock:
                alive[0] += 1
                peak[0] = max(peak[0], alive[0])
            weakref.finalize(record, released)
            return record

    curl_identity()
    ids = [f"UBUNTU-CVE-2026-{n:05d}" for n in range(80)]
    many = {CURL: [{"id": advisory_id, "modified": "1"} for advisory_id in ids]}

    ScanService.refresh(Watched(many), FakeNvd())

    assert len(ProductCheck.objects.get().payload) == 80
    assert peak[0] <= services.FETCH_WORKERS


@pytest.mark.django_db
class TestNoAdvisoryCache:
    """The findings keep what is needed: advisories are downloaded, used, dropped."""

    def test_an_advisory_shared_by_packages_is_downloaded_once_per_run(self):
        curl_identity()
        identify(
            "curl", "8.5.0-2ubuntu10.14", "deb", "ubuntu:24.04", "purl",
            "pkg:deb/ubuntu/curl",
        )
        newer = ("Ubuntu:24.04:LTS", "curl", "8.5.0-2ubuntu10.14")
        shared = [{"id": "UBUNTU-CVE-2026-13608", "modified": "1"}]
        osv_client = FakeOsv({CURL: shared, newer: shared})

        ScanService.refresh(osv_client, FakeNvd())

        assert osv_client.fetched == ["UBUNTU-CVE-2026-13608"]
        assert Finding.objects.count() == 2

    def test_a_changed_advisory_is_downloaded_again_and_replaces_its_findings(self):
        curl_identity()
        ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())
        ProductCheck.objects.update(checked_at=timezone.now() - timedelta(hours=25))
        changed = dict(OSV_RECORDS)
        changed["UBUNTU-CVE-2026-13608"] = json.loads(
            json.dumps(OSV_RECORDS["UBUNTU-CVE-2026-13608"]).replace(
                "8.5.0-2ubuntu10.15", "8.5.0-2ubuntu10.16"
            )
        )
        osv_client = FakeOsv(
            {CURL: [{"id": "UBUNTU-CVE-2026-13608", "modified": "2"}]}, changed
        )

        ScanService.refresh(osv_client, FakeNvd())

        assert osv_client.fetched == ["UBUNTU-CVE-2026-13608"]
        assert Finding.objects.get().fixed_version == "8.5.0-2ubuntu10.16"

    def test_an_advisory_no_longer_listed_removes_its_findings(self):
        curl_identity()
        ScanService.refresh(FakeOsv(CURL_VULNS), FakeNvd())
        ProductCheck.objects.update(checked_at=timezone.now() - timedelta(hours=25))

        ScanService.refresh(FakeOsv({CURL: []}), FakeNvd())

        assert not Finding.objects.exists()
        assert ProductCheck.objects.get().payload == {}

    def test_the_memory_guard_stops_the_scan_cleanly(self):
        curl_identity()
        identify(
            "Tunnelblick", "6.0", "macos", "macos", "cpe", "tunnelblick:tunnelblick"
        )
        osv_client = FakeOsv(CURL_VULNS)
        nvd_client = FakeNvd({"tunnelblick:tunnelblick": TUNNELBLICK_CVES})
        messages = []

        counts = ScanService.refresh(
            osv_client, nvd_client, progress=messages.append, memory=lambda: 10_000
        )

        assert counts["stopped_memory"] == 1
        assert nvd_client.asked == []
        assert not ProductCheck.objects.filter(checked_at__isnull=False).exists()
        assert any("memory" in message for message in messages)
