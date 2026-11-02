import gzip
import io
import json
import shutil
import subprocess
import zipfile
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path

import pytest
from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from automation.scheduler.models import Scheduler
from django.contrib.auth.models import User
from inventory.software.models import AssetPlatform, DistroRelease, SoftwareDictionary
from inventory.software_identity.models import (
    CpeAlias,
    PackageOrigin,
    SoftwareIdentity,
)
from security import reading
from security.cvss import base_score, level
from security.evaluation import Context, EvaluationKey, affected_by
from security.kernel import is_kernel, is_running_kernel
from security.models import (
    SOURCE_EPSS,
    SOURCE_KEV,
    SOURCE_NVD,
    SOURCE_OSV_DEBIAN,
    SOURCE_OSV_UBUNTU,
    EpssScore,
    Evaluation,
    Exclusion,
    Exposure,
    KevEntry,
    NvdCve,
    NvdMatch,
    OsvAdvisory,
    OsvAdvisoryCve,
    OsvAffected,
    ScanLock,
    SecuritySettings,
    SourceSync,
    Vulnerability,
)
from security.scan import ScanService
from security.sources import epss, fetch, kev, nvd, osv
from security.sync import (
    LockBusy,
    SyncService,
    acquire_lock,
    release_lock,
    source_state,
)
from security.versions import dpkg_compare, rpm_compare

DATA = Path(__file__).parent / "test_data"
OSV_RECORDS = json.loads((DATA / "osv_records.json").read_text())
NVD_TUNNELBLICK = json.loads((DATA / "nvd_tunnelblick.json").read_text())
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=dt_timezone.utc)


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
        (
            "linux-image-6.8.0-87-generic",
            "6.8.0-87.88",
            "deb",
            "6.8.0-87-generic",
            True,
        ),  # noqa: E501
        (
            "linux-modules-6.8.0-87-generic:amd64",
            "6.8.0-87.88",
            "deb",
            "6.8.0-87-generic",
            True,
        ),  # noqa: E501
        # an older kernel left installed, a meta package
        (
            "linux-image-6.8.0-85-generic",
            "6.8.0-85.85",
            "deb",
            "6.8.0-87-generic",
            False,
        ),  # noqa: E501
        ("linux-image-generic", "6.8.0.87.88", "deb", "6.8.0-87-generic", False),
        # a container runs the host kernel: no installed package is it
        ("linux-image-6.8.0-87-generic", "6.8.0-87.88", "deb", "6.17.2-1-pve", False),
        ("linux-image-6.8.0-87-generic", "6.8.0-87.88", "deb", "", False),
        (
            "kernel-core",
            "5.14.0-427.13.1.el9_4",
            "rpm",
            "5.14.0-427.13.1.el9_4.x86_64",
            True,
        ),  # noqa: E501
        (
            "kernel-core",
            "0:5.14.0-427.13.1.el9_4",
            "rpm",
            "5.14.0-427.13.1.el9_4.x86_64",
            True,
        ),  # noqa: E501
        (
            "kernel-core",
            "5.14.0-362.8.1.el9_3",
            "rpm",
            "5.14.0-427.13.1.el9_4.x86_64",
            False,
        ),  # noqa: E501
        ("kernel-core", "5.14.0-427.13.1.el9_4", "rpm", "6.17.2-1-pve", False),
    ],
)
def test_running_kernel(name, version, family, running, expected):
    assert is_running_kernel(name, version, family, running) is expected


@pytest.mark.parametrize(
    "name, family, source, expected",
    [
        # built from the kernel source but not the kernel itself
        ("linux-libc-dev:amd64", "deb", "linux", True),
        ("linux-tools-6.8.0-85-generic", "deb", "linux-hwe-6.8", True),
        ("linux-image-6.12.48+deb13-amd64", "deb", "linux-signed-amd64", True),
        ("perf", "rpm", "kernel", True),
        ("curl", "deb", "curl", False),
        ("linux-firmware", "deb", "linux-firmware", False),
    ],
)
def test_kernel_packages_by_source(name, family, source, expected):
    assert is_kernel(name, family, source) is expected


# Versions


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("1.0", "1.0", 0),
        ("1.0~rc1", "1.0", -1),
        ("1.0", "1.0-1", -1),
        ("2:1.0", "1:9", 1),
        ("1.0-1ubuntu1", "1.0-1", 1),
        ("1.2.3", "1.2.10", -1),
        ("1.0a", "1.0", 1),
        ("1.0+dfsg", "1.0", 1),
        ("1.0~", "1.0~~", 1),
        ("2.4.68-1~deb12u1", "2.4.68-1", -1),
        ("8.5.0-2ubuntu10.13", "8.5.0-2ubuntu10.15", -1),
        ("2:4.22.11+dfsg-1~deb13u1", "2:4.22.11+dfsg-1~deb13u2", -1),
    ],
)
def test_dpkg_compare(a, b, expected):
    assert dpkg_compare(a, b) == expected
    assert dpkg_compare(b, a) == -expected


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="needs dpkg")
def test_dpkg_compare_agrees_with_dpkg():
    versions = [
        "0",
        "1",
        "1.0",
        "1.0-1",
        "1.0-1ubuntu0.1",
        "1.0~beta",
        "1.0~~",
        "1.0+b1",
        "1:0.1",
        "1.0a",
        "1.0.a",
        "1.0-1~deb12u1",
        "10.2",
        "9.10",
        "2.30-0ubuntu2",
        "2.30-0ubuntu10",
    ]
    for a in versions:
        for b in versions:
            expected = 0
            for operator, value in (("lt", -1), ("gt", 1)):
                if (
                    subprocess.run(
                        ["dpkg", "--compare-versions", a, operator, b]
                    ).returncode
                    == 0
                ):
                    expected = value
            assert dpkg_compare(a, b) == expected, (a, b)


@pytest.mark.parametrize(
    "a, b, expected",
    [
        ("1.0", "1.0", 0),
        ("1.0~rc1", "1.0", -1),
        ("1.0^post", "1.0", 1),
        ("1:3.0.7-27.el9", "3.0.7-27.el9", 1),
        ("0:2.4.0-1.el9_8", "2.4.0-1.el9_8", 0),
        ("3.0.7-27.el9", "3.0.7-27.el9_4", -1),
        ("3.0.7-27.el9_4.1", "3.0.7-27.el9_4", 1),
        ("2.0", "2.0a", -1),
        ("1.10", "1.9", 1),
        ("1.0010", "1.9", 1),
        # a version without release matches its releases
        ("3.0.7", "3.0.7-27.el9", 0),
    ],
)
def test_rpm_compare(a, b, expected):
    assert rpm_compare(a, b) == expected
    assert rpm_compare(b, a) == -expected


@pytest.mark.parametrize(
    "ranges, versions, installed, expected",
    [
        (
            [[{"introduced": "0"}, {"fixed": "2.4.68-1~deb12u1"}]],
            [],
            "2.4.62-1~deb12u2",
            (True, "2.4.68-1~deb12u1"),
        ),
        (
            [[{"introduced": "0"}, {"fixed": "2.4.68-1~deb12u1"}]],
            [],
            "2.4.68-1~deb12u1",
            (False, ""),
        ),
        # no fix yet
        ([[{"introduced": "0"}]], [], "6.1.76-1", (True, "")),
        ([[{"introduced": "2.0"}, {"fixed": "2.5"}]], [], "1.9", (False, "")),
        ([[{"introduced": "2.0"}, {"last_affected": "2.5"}]], [], "2.5", (True, "")),
        ([[{"introduced": "2.0"}, {"last_affected": "2.5"}]], [], "2.6", (False, "")),
        # several intervals in one range, events out of order
        (
            [
                [
                    {"fixed": "1.5"},
                    {"introduced": "0"},
                    {"introduced": "2.0"},
                    {"fixed": "2.2"},
                ]
            ],
            [],
            "2.1",
            (True, "2.2"),
        ),
        (
            [
                [
                    {"fixed": "1.5"},
                    {"introduced": "0"},
                    {"introduced": "2.0"},
                    {"fixed": "2.2"},
                ]
            ],
            [],
            "1.7",
            (False, ""),
        ),
        ([], ["1.0-1"], "1.0-1", (True, "")),
    ],
)
def test_osv_ranges(ranges, versions, installed, expected):
    affected, fixed, _ = affected_by(ranges, versions, installed, dpkg_compare)
    assert (affected, fixed) == expected


# OSV


@pytest.mark.parametrize(
    "product, platform_key, expected",
    [
        ("pkg:deb/debian/curl", "debian:12", ("Debian:12", None)),
        (
            "pkg:deb/ubuntu/curl",
            "ubuntu:24.04",
            ("Ubuntu:24.04:LTS", "Ubuntu:Pro:24.04:LTS"),
        ),
        ("pkg:deb/ubuntu/curl", "ubuntu:24.10", ("Ubuntu:24.10", None)),
        ("pkg:rpm/rocky/openssl", "rocky:9", ("Rocky Linux:9", None)),
        ("pkg:rpm/almalinux/openssl", "almalinux:9", ("AlmaLinux:9", None)),
        # a package of another distribution than the machine's
        ("pkg:deb/debian/curl", "ubuntu:24.04", (None, None)),
        ("pkg:rpm/redhat/openssl", "rhel:9", (None, None)),
        ("pkg:deb/debian/curl", "", (None, None)),
    ],
)
def test_osv_ecosystems(product, platform_key, expected):
    assert osv.ecosystems(product, platform_key) == expected


@pytest.mark.parametrize(
    "product, expected",
    [
        ("pkg:deb/debian/curl", "curl"),
        ("pkg:deb/debian/libstdc%2B%2B6", "libstdc++6"),
        ("pkg:deb/debian/linux-signed-amd64", "linux"),
        ("pkg:deb/ubuntu/linux-signed-hwe-6.8", "linux-hwe-6.8"),
    ],
)
def test_osv_query_name(product, expected):
    assert osv.query_name(product) == expected


def test_osv_compact_keeps_detection_records_only_with_their_packages():
    debian = osv.compact(OSV_RECORDS["DEBIAN-CVE-2026-29167"], ("DEBIAN-CVE-",))
    reference = osv.compact(
        {"id": "DSA-6000-1", "upstream": ["CVE-2026-29167"], "affected": [{}]},
        ("DEBIAN-CVE-",),
    )

    assert debian["detection"] and debian["cves"] == ["CVE-2026-29167"]
    assert [a["ecosystem"] for a in debian["affected"]] == [
        "Debian:12",
        "Debian:13",
        "Debian:14",
    ]
    assert debian["affected"][0]["urgency"] == "not yet assigned"
    assert (reference["detection"], reference["affected"]) == (False, [])
    assert reference["cves"] == ["CVE-2026-29167"]


def make_zip(path, records):
    with zipfile.ZipFile(path, "w") as archive:
        for record in records:
            archive.writestr(f"{record['id']}.json", json.dumps(record))
    return path


def debian_cve(
    cve, package, fixed=None, ecosystem="Debian:12", urgency="", modified="1"
):
    events = [{"introduced": "0"}] + ([{"fixed": fixed}] if fixed else [])
    return {
        "id": f"DEBIAN-{cve}",
        "modified": modified,
        "upstream": [cve],
        "details": f"{cve} in {package}",
        "affected": [
            {
                "package": {"name": package, "ecosystem": ecosystem},
                "ranges": [{"type": "ECOSYSTEM", "events": events}],
                "ecosystem_specific": {"urgency": urgency},
            }
        ],
    }


@pytest.mark.django_db
class TestOsvLoad:
    def test_load_is_incremental(self, tmp_path):
        first = [
            debian_cve("CVE-2026-1", "curl", "8.0-1"),
            debian_cve("CVE-2026-2", "zlib"),
        ]
        count, details = osv.load(
            SOURCE_OSV_DEBIAN, make_zip(tmp_path / "a.zip", first)
        )

        assert count == 2
        assert details == {"ecosystems": ["Debian:12"]}
        curl = OsvAdvisory.objects.get(advisory_id="DEBIAN-CVE-2026-1")

        second = [
            debian_cve("CVE-2026-1", "curl", "8.0-1"),
            debian_cve("CVE-2026-2", "zlib", "1.3-1", modified="2"),
            debian_cve("CVE-2026-3", "bash"),
        ]
        osv.load(SOURCE_OSV_DEBIAN, make_zip(tmp_path / "b.zip", second))

        # unchanged: the same row; changed: written again
        assert OsvAdvisory.objects.get(advisory_id="DEBIAN-CVE-2026-1").pk == curl.pk
        zlib = OsvAffected.objects.get(package="zlib")
        assert zlib.ranges == [[{"introduced": "0"}, {"fixed": "1.3-1"}]]
        assert OsvAdvisory.objects.count() == 3

    def test_advisories_gone_from_the_archive_are_deleted(self, tmp_path):
        records = [debian_cve(f"CVE-2026-{n}", "curl") for n in range(4)]
        osv.load(SOURCE_OSV_DEBIAN, make_zip(tmp_path / "a.zip", records))

        osv.load(SOURCE_OSV_DEBIAN, make_zip(tmp_path / "b.zip", records[:3]))

        assert OsvAdvisory.objects.count() == 3

    def test_an_archive_with_far_fewer_advisories_is_refused(self, tmp_path):
        records = [debian_cve(f"CVE-2026-{n}", "curl") for n in range(10)]
        osv.load(SOURCE_OSV_DEBIAN, make_zip(tmp_path / "a.zip", records))

        with pytest.raises(ValueError):
            osv.load(SOURCE_OSV_DEBIAN, make_zip(tmp_path / "b.zip", records[:2]))

        assert OsvAdvisory.objects.count() == 10


# NVD


def nvd_item(
    cve_id, criteria, bounds=None, platform=None, status="Analyzed", score=7.5
):
    matches = [{"vulnerable": True, "criteria": criteria, **(bounds or {})}]
    configuration = {"nodes": [{"operator": "OR", "cpeMatch": matches}]}
    if platform:
        configuration = {
            "operator": "AND",
            "nodes": [
                {"operator": "OR", "cpeMatch": matches},
                {
                    "operator": "OR",
                    "cpeMatch": [{"vulnerable": False, "criteria": platform}],
                },
            ],
        }
    return {
        "cve": {
            "id": cve_id,
            "published": "2026-01-01T00:00:00.000",
            "lastModified": "2026-02-01T00:00:00.000",
            "vulnStatus": status,
            "descriptions": [{"lang": "en", "value": f"{cve_id} description"}],
            "metrics": {
                "cvssMetricV31": [
                    {
                        "type": "Primary",
                        "cvssData": {
                            "vectorString": (
                                "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"
                            ),
                            "baseScore": score,
                        },
                    }
                ]
            },
            "configurations": [configuration],
        }
    }


def nvd_feed(path, items):
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump({"format": "NVD_CVE", "vulnerabilities": items}, handle)
    return path


def test_nvd_items_are_read_one_at_a_time():
    document = json.dumps(
        {
            "format": "x",
            "vulnerabilities": [
                {"cve": {"id": f"CVE-2026-{n}", "text": "[]{}," * n}} for n in range(30)
            ],
        }
    )

    items = list(nvd.iter_items(io.StringIO(document), chunk=7))

    assert [item["cve"]["id"] for item in items] == [f"CVE-2026-{n}" for n in range(30)]
    assert list(nvd.iter_items(io.StringIO('{"vulnerabilities": []}'))) == []


def test_nvd_compact_keeps_both_scores_and_the_conditions():
    cve = nvd.compact(NVD_TUNNELBLICK["vulnerabilities"][0]["cve"])
    conditional = nvd.compact(
        nvd_item(
            "CVE-2026-0005",
            "cpe:2.3:a:zoom:meetings:*:*:*:*:*:*:*:*",
            {"versionEndExcluding": "6.0"},
            platform="cpe:2.3:o:apple:macos:-:*:*:*:*:*:*:*",
        )["cve"]
    )

    assert (cve["cvss3_score"], cve["cvss4_score"]) == (5.5, 6.8)
    assert len(cve["matches"]) == 6
    assert not cve["matches"][0]["conditional"]
    assert [m["product"] for m in conditional["matches"]] == ["zoom:meetings"]
    assert conditional["matches"][0]["conditional"]


@pytest.mark.parametrize(
    "version, expected",
    [
        ("6.0", ("nvd_range", "8.0.1", "from 3.5.3 up to 8.0.1 excluded")),
        ("3.3", None),
        ("3.3beta26", ("nvd_exact", "", "version 3.3 beta26")),
        ("9.0beta01", ("nvd_exact", "", "version 9.0 beta01")),
        ("8.0.1", None),
    ],
)
def test_nvd_evaluate(version, expected):
    matches = nvd.compact(NVD_TUNNELBLICK["vulnerabilities"][0]["cve"])["matches"]

    result = nvd.evaluate(matches, version)

    if expected is None:
        assert result is None
    else:
        assert (
            result["method"],
            result["fixed_version"],
            result["affected_range"],
        ) == expected
        assert result["uncertain"] is False


def test_nvd_all_versions_and_conditions_are_uncertain():
    everything = {
        "criteria": "cpe:2.3:a:7-zip:7-zip:*:*:*:*:*:*:*:*",
        "bounds": {},
        "conditional": False,
    }
    conditional = {
        "criteria": "cpe:2.3:a:7-zip:7-zip:*:*:*:*:*:*:*:*",
        "bounds": {"versionEndExcluding": "25.0"},
        "conditional": True,
    }

    assert nvd.evaluate([everything], "24.08")["uncertain"] is True
    result = nvd.evaluate([everything, conditional], "24.08")
    assert (result["method"], result["uncertain"]) == ("nvd_range", True)


@pytest.mark.django_db
def test_nvd_year_load_replaces_the_year(tmp_path):
    items = [
        nvd_item(
            "CVE-2026-0001",
            "cpe:2.3:a:mozilla:firefox:*:*:*:*:*:*:*:*",
            {"versionEndExcluding": "140.0"},
        ),
        nvd_item("CVE-2025-0009", "cpe:2.3:a:mozilla:firefox:*:*:*:*:*:*:*:*"),
    ]
    assert nvd.load_year(2026, nvd_feed(tmp_path / "a.gz", items), full=True) == 1
    assert NvdMatch.objects.get().vendor_product == "mozilla:firefox"

    assert nvd.load_year(2026, nvd_feed(tmp_path / "b.gz", items), full=False) == 1
    cve = NvdCve.objects.get()
    assert (cve.full, cve.cvss3_score, cve.description) == (False, 7.5, "")
    assert not NvdMatch.objects.exists()


# KEV and EPSS


@pytest.mark.django_db
def test_kev_and_epss_load(tmp_path):
    catalog = tmp_path / "kev.json"
    catalog.write_text(
        json.dumps(
            {
                "catalogVersion": "2026.11.01",
                "vulnerabilities": [
                    {
                        "cveID": "CVE-2026-1",
                        "dateAdded": "2026-10-01",
                        "knownRansomwareCampaignUse": "Known",
                    }
                ],
            }
        )
    )
    scores = tmp_path / "epss.csv.gz"
    with gzip.open(scores, "wt") as handle:
        handle.write("#model_version:v2025.03.14,score_date:2026-11-01T00:00:00+0000\n")
        handle.write("cve,epss,percentile\nCVE-2026-1,0.91,0.99\nCVE-2026-2,0.01,0.2\n")

    assert kev.load(catalog) == (1, {"catalog_version": "2026.11.01"})
    count, details = epss.load(scores)

    assert count == 2 and details["score_date"].startswith("2026-11-01")
    entry = KevEntry.objects.get()
    assert (entry.date_added, entry.ransomware) == (date(2026, 10, 1), True)
    assert EpssScore.objects.get(cve="CVE-2026-1").score == 0.91


# Synchronization


class FakeResponse:
    def __init__(self, body=b"", status=200, headers=None):
        self.body, self.status_code, self.headers = body, status, headers or {}

    def iter_content(self, size):
        yield self.body


class FakeServer:
    """{url: bytes, or an Exception}; answers 304 to a matching ETag."""

    def __init__(self, files):
        self.files = files
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        body = self.files[url]
        if isinstance(body, Exception):
            raise body
        etag = f'"{len(body)}"'
        if headers.get("If-None-Match") == etag:
            return FakeResponse(status=304)
        return FakeResponse(body, headers={"ETag": etag})


def zip_bytes(records):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for record in records:
            archive.writestr(f"{record['id']}.json", json.dumps(record))
    return buffer.getvalue()


DEBIAN_URL = "https://osv.test/Debian/all.zip"


@pytest.fixture
def osv_test_url(settings):
    settings.OSV_DATA_URL = "https://osv.test"
    settings.NVD_CVE_FEED_URL = "https://nvd.test/nvdcve-2.0-{year}.json.gz"
    settings.KEV_URL = "https://kev.test/kev.json"
    settings.EPSS_URL = "https://epss.test/epss.csv.gz"


@pytest.mark.django_db
class TestSync:
    def test_a_failed_source_keeps_its_data_and_becomes_stale(self, osv_test_url):
        server = FakeServer({DEBIAN_URL: zip_bytes([debian_cve("CVE-2026-1", "curl")])})
        assert SyncService.run([SOURCE_OSV_DEBIAN], now=NOW, get=server) == {
            SOURCE_OSV_DEBIAN: "loaded"
        }

        server.files[DEBIAN_URL] = OSError("network down")
        later = NOW + timedelta(hours=49)
        results = SyncService.run([SOURCE_OSV_DEBIAN], now=later, get=server)

        sync = SourceSync.objects.get(source=SOURCE_OSV_DEBIAN)
        assert "network down" in results[SOURCE_OSV_DEBIAN]
        assert OsvAdvisory.objects.count() == 1
        assert (sync.last_success, sync.last_attempt) == (NOW, later)
        assert source_state(sync, later) == "stale"
        assert source_state(sync, NOW + timedelta(hours=47)) == "fresh"
        assert source_state(None, NOW) == "never_loaded"

    def test_an_unchanged_file_is_not_loaded_again(self, osv_test_url):
        server = FakeServer({DEBIAN_URL: zip_bytes([debian_cve("CVE-2026-1", "curl")])})
        SyncService.run([SOURCE_OSV_DEBIAN], now=NOW, get=server)

        later = NOW + timedelta(days=1)
        results = SyncService.run([SOURCE_OSV_DEBIAN], now=later, get=server)

        assert results == {SOURCE_OSV_DEBIAN: "unchanged"}
        assert SourceSync.objects.get(source=SOURCE_OSV_DEBIAN).last_success == later

    def test_nvd_loads_the_window_with_matches_and_older_years_scores(
        self, osv_test_url, tmp_path
    ):
        SecuritySettings.objects.update_or_create(id=1, defaults={"nvd_years": 2})
        files = {}
        for year in range(2002, 2027):
            item = nvd_item(
                f"CVE-{year}-0001", "cpe:2.3:a:mozilla:firefox:*:*:*:*:*:*:*:*"
            )
            body = gzip.compress(json.dumps({"vulnerabilities": [item]}).encode())
            files[f"https://nvd.test/nvdcve-2.0-{year}.json.gz"] = body
            files[f"https://nvd.test/nvdcve-2.0-{year}.meta"] = (
                f"sha256:{year}\n".encode()
            )
        server = FakeServer(files)

        SyncService.run([SOURCE_NVD], now=NOW, get=server)

        assert set(NvdCve.objects.filter(full=True).values_list("year", flat=True)) == {
            2025,
            2026,
        }
        assert NvdCve.objects.filter(full=False).count() == 23
        assert NvdMatch.objects.count() == 2

        # the next day: unchanged metas, older years not even checked
        server.calls.clear()
        SyncService.run([SOURCE_NVD], now=NOW + timedelta(days=1), get=server)
        assert sorted(server.calls) == [
            "https://nvd.test/nvdcve-2.0-2025.meta",
            "https://nvd.test/nvdcve-2.0-2026.meta",
        ]

        # a wider window loads 2024 with its matches
        SecuritySettings.objects.update(nvd_years=3)
        SyncService.run([SOURCE_NVD], now=NOW + timedelta(days=2), get=server)
        assert NvdCve.objects.get(year=2024).full

    def test_kev_and_epss_sources(self, osv_test_url):
        catalog = json.dumps({"vulnerabilities": [{"cveID": "CVE-2026-1"}]}).encode()
        scores = gzip.compress(b"cve,epss,percentile\nCVE-2026-1,0.5,0.9\n")
        server = FakeServer(
            {
                "https://kev.test/kev.json": catalog,
                "https://epss.test/epss.csv.gz": scores,
            }
        )

        assert SyncService.run([SOURCE_KEV, SOURCE_EPSS], now=NOW, get=server) == {
            SOURCE_KEV: "loaded",
            SOURCE_EPSS: "loaded",
        }


@pytest.mark.django_db
class TestLock:
    def test_one_run_at_a_time_taken_over_after_12_hours(self):
        acquire_lock(NOW)

        with pytest.raises(LockBusy):
            acquire_lock(NOW + timedelta(hours=11))
        assert acquire_lock(NOW + timedelta(hours=13))
        assert ScanLock.objects.get().acquired_at == NOW + timedelta(hours=13)

        release_lock()
        assert not ScanLock.objects.exists()


def test_download_raises_unchanged_on_304():
    server = FakeServer({"https://x.test/f": b"data"})
    path, fingerprint = fetch.download("https://x.test/f", {}, get=server)
    Path(path).unlink()

    with pytest.raises(fetch.Unchanged):
        fetch.download("https://x.test/f", fingerprint, get=server)


# Scan


def make_asset(name, family="deb", key="debian:12", running=""):
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
    AssetPlatform.objects.create(
        asset=asset, family=family, key=key, running_kernel=running
    )
    return asset


def install(
    asset,
    name,
    version,
    product="",
    identity_version=None,
    status="matched",
    family="deb",
    key="debian:12",
    origin="Debian",
    reason="",
):
    """A dictionary entry on a machine, with its identity."""
    scheme = "purl" if family in ("deb", "rpm") else "cpe"
    entry, _ = SoftwareDictionary.objects.get_or_create(
        name=name,
        version=version,
        platform_family=family,
        platform_key=key,
        package_origin=origin,
    )
    entry.assets.add(asset)
    if status is not None:
        SoftwareIdentity.objects.update_or_create(
            entry=entry,
            defaults={
                "family": family,
                "status": status,
                "reason": reason,
                "scheme": scheme if product else "",
                "product": product,
                "version": identity_version or version,
            },
        )
    return entry


def uninstall(asset, entry):
    entry.assets.remove(asset)


def loaded(*sources, at=NOW, ecosystems=()):
    for source in sources:
        SourceSync.objects.update_or_create(
            source=source,
            defaults={
                "last_success": at,
                "last_attempt": at,
                "details": {"ecosystems": list(ecosystems)},
            },
        )


def advisory(source, advisory_id, cves, rows, rating="", withdrawn=False, vector=""):
    record = OsvAdvisory.objects.create(
        source=source,
        advisory_id=advisory_id,
        cves=cves,
        rating=rating,
        withdrawn=withdrawn,
        cvss_vector=vector,
        summary=f"{advisory_id} summary",
    )
    for cve in cves:
        OsvAdvisoryCve.objects.create(advisory=record, cve=cve)
    for ecosystem, package, events, urgency in rows:
        OsvAffected.objects.create(
            advisory=record,
            ecosystem=ecosystem,
            package=package,
            ranges=[events],
            urgency=urgency,
        )
    return record


def fixed_in(version):
    return [{"introduced": "0"}, {"fixed": version}]


UNFIXED = [{"introduced": "0"}]


def open_exposures(asset=None):
    exposures = Exposure.objects.filter(closed_at__isnull=True)
    if asset is not None:
        exposures = exposures.filter(asset=asset)
    return sorted(
        exposures.values_list("vulnerability__vuln_id", "version", "fixed_version")
    )


def closed(asset):
    return sorted(
        Exposure.objects.filter(asset=asset, closed_at__isnull=False).values_list(
            "vulnerability__vuln_id", "resolution"
        )
    )


@pytest.fixture
def debian_data(db):
    loaded(SOURCE_OSV_DEBIAN, ecosystems=["Debian:12", "Debian:13"])
    advisory(
        SOURCE_OSV_DEBIAN,
        "DEBIAN-CVE-2026-1",
        ["CVE-2026-1"],
        [("Debian:12", "curl", fixed_in("8.0-2"), "medium")],
    )
    advisory(
        SOURCE_OSV_DEBIAN,
        "DEBIAN-CVE-2026-2",
        ["CVE-2026-2"],
        [("Debian:12", "curl", UNFIXED, "unimportant")],
    )


CURL = "pkg:deb/debian/curl"


@pytest.mark.django_db
class TestScan:
    def test_findings_are_evaluated_once_and_copied_to_machines(self, debian_data):
        first, second = make_asset("a"), make_asset("b")
        install(first, "curl", "8.0-1", CURL)
        install(second, "curl", "8.0-1", CURL)

        counts = ScanService.run(now=NOW)

        assert counts["evaluated"] == 1
        assert Evaluation.objects.count() == 1
        assert open_exposures(first) == [
            ("CVE-2026-1", "8.0-1", "8.0-2"),
            ("CVE-2026-2", "8.0-1", ""),
        ]
        assert open_exposures(second) == open_exposures(first)

    def test_the_source_version_is_compared(self, debian_data):
        # libcurl4 is built from curl: its own version is not curl's
        asset = make_asset("a")
        install(asset, "libcurl4", "9.9-1", CURL, identity_version="8.0-2")

        ScanService.run(now=NOW)

        assert open_exposures(asset) == [("CVE-2026-2", "8.0-2", "")]

    def test_a_new_version_fixes_and_an_uninstall_closes(self, debian_data):
        asset = make_asset("a")
        old = install(asset, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        uninstall(asset, old)
        install(asset, "curl", "8.0-2", CURL)
        ScanService.run(now=NOW + timedelta(hours=1))

        assert closed(asset) == [("CVE-2026-1", "fixed")]
        assert open_exposures(asset) == [("CVE-2026-2", "8.0-2", "")]

        uninstall(asset, SoftwareDictionary.objects.get(version="8.0-2"))
        ScanService.run(now=NOW + timedelta(hours=2))

        assert closed(asset) == [("CVE-2026-1", "fixed"), ("CVE-2026-2", "uninstalled")]

    def test_a_withdrawn_advisory_closes_on_fresh_data(self, debian_data):
        asset = make_asset("a")
        install(asset, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        OsvAdvisory.objects.filter(advisory_id="DEBIAN-CVE-2026-2").update(
            withdrawn=True
        )
        loaded(
            SOURCE_OSV_DEBIAN, at=NOW + timedelta(hours=24), ecosystems=["Debian:12"]
        )
        ScanService.run(now=NOW + timedelta(hours=25))

        assert closed(asset) == [("CVE-2026-2", "withdrawn")]

    def test_losing_data_never_closes(self, debian_data):
        asset = make_asset("a")
        install(asset, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        # the source failed for three days, then its advisories went away
        OsvAdvisory.objects.all().delete()
        ScanService.run(now=NOW + timedelta(hours=72))

        assert closed(asset) == []
        assert len(open_exposures(asset)) == 2

    def test_a_new_version_waiting_for_its_evaluation_closes_nothing(self, debian_data):
        asset = make_asset("a")
        old = install(asset, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        uninstall(asset, old)
        install(asset, "curl", "8.0-2", CURL)
        # the source never loaded since: the new version cannot be checked
        SourceSync.objects.update(last_success=NOW - timedelta(hours=72))
        ScanService.run(now=NOW + timedelta(hours=1))

        assert closed(asset) == []

    def test_an_identity_out_of_coverage_closes(self, debian_data):
        asset = make_asset("a")
        entry = install(asset, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        SoftwareIdentity.objects.filter(entry=entry).update(
            status="unsupported", reason="third_party", scheme="", product=""
        )
        ScanService.run(now=NOW + timedelta(hours=1))

        assert closed(asset) == [
            ("CVE-2026-1", "identity_changed"),
            ("CVE-2026-2", "identity_changed"),
        ]

    def test_only_the_running_kernel_counts(self, db):
        loaded(SOURCE_OSV_DEBIAN, ecosystems=["Debian:12"])
        advisory(
            SOURCE_OSV_DEBIAN,
            "DEBIAN-CVE-2026-9",
            ["CVE-2026-9"],
            [("Debian:12", "linux", fixed_in("6.1.90-1"), "")],
        )
        asset = make_asset("a", running="6.1.0-20-amd64")
        install(
            asset,
            "linux-image-6.1.0-18-amd64",
            "6.1.76-1",
            "pkg:deb/debian/linux-signed-amd64",
        )
        running = install(
            asset,
            "linux-image-6.1.0-20-amd64",
            "6.1.85-1",
            "pkg:deb/debian/linux-signed-amd64",
        )
        container = make_asset("c", running="6.17.2-1-pve")
        install(
            container,
            "linux-image-6.1.0-20-amd64",
            "6.1.85-1",
            "pkg:deb/debian/linux-signed-amd64",
        )

        ScanService.run(now=NOW)

        assert open_exposures(asset) == [("CVE-2026-9", "6.1.85-1", "6.1.90-1")]
        assert open_exposures(container) == []
        assert (
            reading.coverage(container.id, now=NOW)["kernel"]
            == "host_kernel_unverified"
        )

        # a new running kernel with the fix
        install(
            asset,
            "linux-image-6.1.0-22-amd64",
            "6.1.90-1",
            "pkg:deb/debian/linux-signed-amd64",
        )
        AssetPlatform.objects.filter(asset=asset).update(
            running_kernel="6.1.0-22-amd64"
        )
        ScanService.run(now=NOW + timedelta(hours=1))
        assert closed(asset) == [("CVE-2026-9", "fixed")]
        del running

    def test_ubuntu_pro_after_standard_support(self, db):
        loaded(
            SOURCE_OSV_UBUNTU,
            ecosystems=[
                "Ubuntu:18.04:LTS",
                "Ubuntu:Pro:18.04:LTS",
                "Ubuntu:24.04:LTS",
                "Ubuntu:Pro:24.04:LTS",
            ],
        )
        advisory(
            SOURCE_OSV_UBUNTU,
            "UBUNTU-CVE-2026-5",
            ["CVE-2026-5"],
            [
                ("Ubuntu:18.04:LTS", "curl", UNFIXED, ""),
                (
                    "Ubuntu:Pro:18.04:LTS",
                    "curl",
                    fixed_in("7.58.0-2ubuntu3.24+esm5"),
                    "",
                ),
                ("Ubuntu:24.04:LTS", "curl", fixed_in("8.5.0-2ubuntu10.15"), ""),
                (
                    "Ubuntu:Pro:24.04:LTS",
                    "curl",
                    fixed_in("8.5.0-2ubuntu10.14+esm1"),
                    "",
                ),
            ],
        )
        bionic = make_asset("bionic", key="ubuntu:18.04")
        install(
            bionic,
            "curl",
            "7.58.0-2ubuntu3.24",
            "pkg:deb/ubuntu/curl",
            key="ubuntu:18.04",
            origin="Ubuntu",
        )
        patched = make_asset("patched", key="ubuntu:18.04")
        install(
            patched,
            "curl",
            "7.58.0-2ubuntu3.24+esm5",
            "pkg:deb/ubuntu/curl",
            key="ubuntu:18.04",
            origin="UbuntuESM",
        )
        noble = make_asset("noble", key="ubuntu:24.04")
        install(
            noble,
            "curl",
            "8.5.0-2ubuntu10.13",
            "pkg:deb/ubuntu/curl",
            key="ubuntu:24.04",
            origin="Ubuntu",
        )

        ScanService.run(now=NOW)

        exposure = Exposure.objects.get(asset=bionic)
        assert (exposure.fixed_version, exposure.fix_channel) == (
            "7.58.0-2ubuntu3.24+esm5",
            "ubuntu_pro",
        )
        assert open_exposures(patched) == []
        # standard support: the standard fix comes first
        exposure = Exposure.objects.get(asset=noble)
        assert (exposure.fixed_version, exposure.fix_channel) == (
            "8.5.0-2ubuntu10.15",
            "",
        )

    def test_a_release_no_longer_followed(self, debian_data):
        asset = make_asset("a", key="debian:10")
        install(asset, "curl", "7.64.0-4", CURL, key="debian:10")

        ScanService.run(now=NOW)

        assert open_exposures(asset) == []
        rows = reading.asset_software_states(asset.id, now=NOW)
        assert [row["state"] for row in rows] == ["release_not_tracked"]


@pytest.mark.django_db
class TestNvdScan:
    @pytest.fixture
    def nvd_data(self, tmp_path):
        SecuritySettings.objects.update_or_create(id=1, defaults={"nvd_years": 3})
        loaded(SOURCE_NVD)
        nvd.load_year(
            2026,
            nvd_feed(
                tmp_path / "2026.gz",
                [
                    nvd_item(
                        "CVE-2026-0100",
                        "cpe:2.3:a:zoom:meetings:*:*:*:*:*:*:*:*",
                        {"versionEndExcluding": "6.2"},
                    ),
                    nvd_item("CVE-2026-0101", "cpe:2.3:a:zoom:zoom:*:*:*:*:*:*:*:*"),
                    nvd_item(
                        "CVE-2026-0102",
                        "cpe:2.3:a:zoom:zoom:*:*:*:*:*:*:*:*",
                        {"versionEndExcluding": "6.0"},
                        status="Rejected",
                    ),
                ],
            ),
            full=True,
        )
        nvd.load_year(
            2024,
            nvd_feed(
                tmp_path / "2024.gz",
                [
                    nvd_item(
                        "CVE-2024-0001",
                        "cpe:2.3:a:zoom:zoom:*:*:*:*:*:*:*:*",
                        {"versionEndExcluding": "7.0"},
                    )
                ],
            ),
            full=True,
        )

    def test_aliases_ranges_and_all_versions(self, nvd_data):
        asset = make_asset("w", family="windows", key="windows")
        install(
            asset,
            "Zoom Workplace",
            "6.1.5",
            "zoom:zoom",
            family="windows",
            key="windows",
            origin=None,
        )

        ScanService.run(now=NOW)

        rows = Exposure.objects.filter(asset=asset).order_by("vulnerability__vuln_id")
        assert [(e.vulnerability.vuln_id, e.method, e.uncertain) for e in rows] == [
            ("CVE-2024-0001", "nvd_range", False),
            ("CVE-2026-0100", "nvd_range", False),
            ("CVE-2026-0101", "nvd_all_versions", True),
        ]
        assert CpeAlias.objects.filter(
            product="zoom:zoom", alias="zoom:meetings"
        ).exists()

    def test_a_year_out_of_the_window_closes_its_exposures(self, nvd_data):
        asset = make_asset("w", family="windows", key="windows")
        install(
            asset,
            "Zoom Workplace",
            "6.1.5",
            "zoom:zoom",
            family="windows",
            key="windows",
            origin=None,
        )
        ScanService.run(now=NOW)

        SecuritySettings.objects.update(nvd_years=2)
        loaded(SOURCE_NVD, at=NOW + timedelta(hours=24))
        ScanService.run(now=NOW + timedelta(hours=25))

        assert closed(asset) == [("CVE-2024-0001", "out_of_window")]

    def test_scores_kev_and_epss_are_read(self, nvd_data):
        KevEntry.objects.create(cve="CVE-2026-0100", date_added=date(2026, 10, 1))
        EpssScore.objects.create(cve="CVE-2026-0100", score=0.9, percentile=0.99)
        asset = make_asset("w", family="windows", key="windows")
        install(
            asset,
            "Zoom Workplace",
            "6.1.5",
            "zoom:zoom",
            family="windows",
            key="windows",
            origin=None,
        )

        ScanService.run(now=NOW)

        vulnerability = Vulnerability.objects.get(vuln_id="CVE-2026-0100")
        assert (vulnerability.kev, vulnerability.epss, vulnerability.cvss_score) == (
            True,
            0.9,
            7.5,
        )
        assert vulnerability.cvss_version == "3.1"


@pytest.mark.django_db
class TestInstallationStates:
    def test_each_test_in_order(self, debian_data):
        asset = make_asset("a")
        install(asset, "curl", "8.0-1", CURL)
        install(asset, "nginx", "1.0", "", status="review")
        install(
            asset, "docker-ce", "1.0", "", status="unsupported", reason="third_party"
        )
        install(asset, "rh-tool", "1.0", "pkg:rpm/redhat/tool")
        install(asset, "bash", "5.2-1", "pkg:deb/debian/bash")

        states = {
            row["name"]: row["state"]
            for row in reading.asset_software_states(asset.id, now=NOW)
        }
        assert states == {
            "curl": "pending",
            "nginx": "no_identity",
            "docker-ce": "third_party",
            "rh-tool": "not_handled",
            "bash": "pending",
        }

        ScanService.run(now=NOW)
        states = {
            row["name"]: row["state"]
            for row in reading.asset_software_states(asset.id, now=NOW)
        }
        assert states["curl"] == states["bash"] == "checked"

        later = NOW + timedelta(hours=49)
        states = {
            row["name"]: row["state"]
            for row in reading.asset_software_states(asset.id, now=later)
        }
        assert states["curl"] == "stale"

        Exclusion.objects.create(asset=asset, comment="lab machine")
        states = {
            row["name"]: row["state"]
            for row in reading.asset_software_states(asset.id, now=NOW)
        }
        assert set(states.values()) == {"excluded"}

    def test_a_source_never_loaded(self, db):
        asset = make_asset("a")
        install(asset, "curl", "8.0-1", CURL)

        ScanService.run(now=NOW)

        assert [
            row["state"] for row in reading.asset_software_states(asset.id, now=NOW)
        ] == ["source_never_loaded"]


@pytest.mark.django_db
class TestReading:
    def test_priority_noise_and_exclusions(self, debian_data):
        KevEntry.objects.create(cve="CVE-2026-1")
        first, second = make_asset("a"), make_asset("b")
        install(first, "curl", "8.0-1", CURL)
        install(second, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        rows, hidden, order = reading.vulnerability_rows(now=NOW)
        assert [row["vuln_id"] for row in rows] == ["CVE-2026-1"]
        assert hidden == {"minor_distro": 2}
        assert order == ["kev", "score", "epss", "machines"]
        assert (rows[0]["kev"], rows[0]["machines"]) == (True, 2)

        rows, hidden, _ = reading.vulnerability_rows(show=["minor_distro"], now=NOW)
        assert {row["vuln_id"] for row in rows} == {"CVE-2026-1", "CVE-2026-2"}

        Exclusion.objects.create(asset=first, vuln_id="CVE-2026-1", comment="mitigated")
        user = User.objects.create(username="owner")
        group = AssetGroup.objects.create(
            name="lab", user=user, visibility="public", is_dynamic=True
        )
        group.assets.add(second)
        Exclusion.objects.create(
            group=group, comment="lab", expires_at=NOW - timedelta(days=1)
        )
        rows, _, _ = reading.vulnerability_rows(now=NOW)
        assert rows[0]["machines"] == 1

        Exclusion.objects.create(group=group, comment="lab")
        rows, _, _ = reading.vulnerability_rows(now=NOW)
        assert rows == []
        # exclusions are never stored on the exposures
        assert Exposure.objects.filter(closed_at__isnull=True).count() == 4


@pytest.mark.django_db
class TestApi:
    def test_list_detail_and_exposures(self, api_client, debian_data):
        asset = make_asset("a")
        install(asset, "curl", "8.0-1", CURL)
        ScanService.run(now=NOW)

        response = api_client.get(
            "/vulnerabilities/?show=minor_distro&ordering=machines,score"
        )
        assert response.status_code == 200
        assert response.data["ordering"] == ["machines", "score"]
        assert response.data["count"] == 2

        detail = api_client.get("/vulnerabilities/CVE-2026-1/").data
        assert [row["asset"] for row in detail["open"]] == [asset.id]
        assert detail["references"][0]["id"] == "DEBIAN-CVE-2026-1"

        exposures = api_client.get(f"/vulnerability_exposures/?asset={asset.id}").data
        assert {row["vuln_id"] for row in exposures} == {"CVE-2026-1", "CVE-2026-2"}
        software = api_client.get(
            f"/vulnerability_exposures/software/?asset={asset.id}"
        )
        assert software.data[0]["state"] in ("checked", "stale")

        coverage = api_client.get("/vulnerabilities/coverage/").data
        assert coverage["families"][0]["family"] == "deb"
        assert {
            row["source"] for row in api_client.get("/vulnerabilities/sources/").data
        } >= {
            "osv_debian",
            "nvd",
            "kev",
            "epss",
        }

    @pytest.mark.parametrize(
        "params",
        [
            "level=severe",
            "fix=maybe",
            "ordering=name",
            "ordering=kev,kev",
            "show=all",
            "asset=x",
        ],
    )
    def test_invalid_parameters(self, api_client, params):
        assert api_client.get(f"/vulnerabilities/?{params}").status_code == 400

    def test_exposures_need_a_machine(self, api_client):
        assert api_client.get("/vulnerability_exposures/").status_code == 400

    def test_exclusions_need_a_comment_and_one_target(self, api_client, admin_user):
        asset = make_asset("a")
        group = AssetGroup.objects.create(
            name="g", user=admin_user, visibility="public"
        )

        assert (
            api_client.post(
                "/vulnerability_exclusions/", {"asset": asset.id, "comment": " "}
            ).status_code
            == 400
        )
        assert (
            api_client.post(
                "/vulnerability_exclusions/",
                {"asset": asset.id, "group": group.id, "comment": "x"},
            ).status_code
            == 400
        )
        response = api_client.post(
            "/vulnerability_exclusions/",
            {"group": group.id, "vuln_id": "cve-2026-1", "comment": "accepted risk"},
        )
        assert response.status_code == 201, response.data
        exclusion = Exclusion.objects.get()
        assert (exclusion.vuln_id, exclusion.user) == (
            "CVE-2026-1",
            User.objects.get(username="test-superuser"),
        )

    def test_settings(self, api_client):
        current = api_client.get("/security_settings/").data
        assert current["priority"] == ["kev", "score", "epss", "machines"]

        bad = api_client.patch(
            f"/security_settings/{current['id']}/",
            {"priority": ["kev", "x"]},
            format="json",
        )
        assert bad.status_code == 400
        response = api_client.patch(
            f"/security_settings/{current['id']}/",
            {"nvd_years": 5, "cpe_match_score": 0.95},
            format="json",
        )
        assert response.status_code == 200
        assert SecuritySettings.current().nvd_years == 5

    def test_a_user_without_permission_is_refused(self, make_api_client):
        nobody = make_api_client()
        assert nobody.get("/vulnerabilities/").status_code == 403


@pytest.mark.django_db
def test_seeds():
    tasks = dict(
        Scheduler.objects.filter(
            name__in=[
                "securitySync.SecuritySync",
                "vulnerabilityScan.VulnerabilityScan",
            ]
        ).values_list("name", "active")
    )
    assert tasks == {
        "securitySync.SecuritySync": False,
        "vulnerabilityScan.VulnerabilityScan": False,
    }
    assert SecuritySettings.objects.count() == 1
    assert DistroRelease.objects.filter(standard_support_end__isnull=False).exists()
    assert PackageOrigin.objects.filter(extended=True).count() == 2


@pytest.mark.django_db
def test_incremental_scan_takes_the_machines_inventoried_since(debian_data):
    asset = make_asset("a")
    install(asset, "curl", "8.0-1", CURL)
    ScanService.run(now=NOW)
    other = make_asset("b")
    install(other, "curl", "8.0-1", CURL)

    ScanService.incremental(now=NOW + timedelta(hours=1))

    assert len(open_exposures(other)) == 2


def test_cvss_v4_vectors_have_no_computed_score():
    assert (
        base_score("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")
        is None
    )
    assert level(None, "") == "unknown"


def test_context_keys_are_per_platform_and_extended_repository():
    key = EvaluationKey("purl", CURL, "8.0-1", "debian:12", False)
    assert key._replace(extended=True) != key
    assert Context.__name__ == "Context"


@pytest.mark.django_db
def test_incremental_scan_takes_machines_whose_software_got_an_identity(debian_data):
    asset = make_asset("a")
    entry = install(asset, "curl", "8.0-1", CURL, status=None)
    ScanService.run(now=NOW)
    InventoryBase.objects.filter(pk=asset.pk).update(
        last_update=NOW - timedelta(days=1)
    )
    AssetPlatform.objects.filter(asset=asset).update(updated_at=NOW - timedelta(days=1))

    SoftwareIdentity.objects.create(
        entry=entry,
        family="deb",
        status="matched",
        scheme="purl",
        product=CURL,
        version="8.0-1",
    )
    ScanService.incremental(now=NOW + timedelta(hours=1))

    assert len(open_exposures(asset)) == 2
