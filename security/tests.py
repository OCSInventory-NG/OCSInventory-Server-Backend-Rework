import json
from pathlib import Path

import pytest
from django.db import IntegrityError
from security.cvss import base_score, level
from security.kernel import is_kernel, is_running_kernel
from security.sources import osv
from security.models import Finding, ProductCheck, Vulnerability


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
