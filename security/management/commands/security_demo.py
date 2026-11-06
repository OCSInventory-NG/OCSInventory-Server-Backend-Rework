"""
Demo data for the vulnerability screens, for a development database only (it
writes fake source states): machines, software, identities and a
small set of advisories and CVEs, then two real scans (ten days ago and now)
so that open and closed exposures, every installation state and every
resolution show up. Fictitious identifiers only (CVE-2026-9xxxx...).

    python manage.py security_demo           # (re)create the demo
    python manage.py security_demo --reset   # remove it
"""

from datetime import date, timedelta

from asset.asset_group.models import AssetGroup
from asset.inventory_base.models import InventoryBase
from config.models import Config
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from inventory.software.models import AssetPlatform, SoftwareDictionary
from inventory.software_identity.models import SoftwareIdentity
from inventory.software_identity.normalizers import build_normalizers
from inventory.software_identity.normalizers.cpe import cpe_identifier, cpe_version
from inventory.software_identity.services import IdentityService
from security import config as security_config
from security.models import (
    SOURCE_EPSS,
    SOURCE_KEV,
    SOURCE_NVD,
    SOURCE_OSV_ALMA,
    SOURCE_OSV_DEBIAN,
    SOURCE_OSV_ROCKY,
    SOURCE_OSV_UBUNTU,
    EpssScore,
    Evaluation,
    Exclusion,
    KevEntry,
    NvdCve,
    NvdMatch,
    OsvAdvisory,
    OsvAdvisoryCve,
    OsvAffected,
    SourceSync,
    Vulnerability,
)
from security.scan import ScanService

PREFIX = "demo-security-"
GROUP = "Demo security lab"

# Machines: name, family, platform key, os-release values, running kernel
MACHINES = [
    (
        "srv-web-01",
        "deb",
        "debian:12",
        ("debian", "", "12", "bookworm"),
        "6.1.0-25-amd64",
    ),
    (
        "srv-db-01",
        "deb",
        "debian:12",
        ("debian", "", "12", "bookworm"),
        "6.1.0-25-amd64",
    ),
    (
        "ubuntu-legacy-01",
        "deb",
        "ubuntu:18.04",
        ("ubuntu", "debian", "18.04", "bionic"),
        "4.15.0-213-generic",
    ),
    (
        "ubuntu-desk-01",
        "deb",
        "ubuntu:24.04",
        ("ubuntu", "debian", "24.04", "noble"),
        "6.8.0-45-generic",
    ),
    (
        "rocky-app-01",
        "rpm",
        "rocky:9",
        ("rocky", "rhel centos fedora", "9.4", ""),
        "5.14.0-427.13.1.el9_4.x86_64",
    ),
    (
        "alma-app-01",
        "rpm",
        "almalinux:9",
        ("almalinux", "rhel centos fedora", "9.4", ""),
        "5.14.0-427.13.1.el9_4.x86_64",
    ),
    (
        "container-01",
        "deb",
        "debian:12",
        ("debian", "", "12", "bookworm"),
        "6.17.2-1-pve",
    ),
    ("lab-01", "deb", "debian:12", ("debian", "", "12", "bookworm"), "6.1.0-25-amd64"),
    (
        "win-pc-01",
        "windows",
        "windows",
        ("Microsoft Windows 11 Pro", "", "10.0.26100", ""),
        "",
    ),
    ("mac-01", "macos", "macos", ("macOS", "", "15.1", ""), ""),
]

# Linux packages: (name, version, source, source version, origin), per
# machine, before (ten days ago) and now
DEB = "Debian"
CURL_OLD = ("curl", "7.88.1-10+deb12u5", "curl", "7.88.1-10+deb12u5", DEB)
CURL_NEW = ("curl", "7.88.1-10+deb12u8", "curl", "7.88.1-10+deb12u8", DEB)
OPENSSL_12 = ("libssl3:amd64", "3.0.13-1~deb12u1", "openssl", "3.0.13-1~deb12u1", DEB)
APACHE = ("apache2", "2.4.62-1~deb12u1", "apache2", "2.4.62-1~deb12u1", DEB)
LIBLDB = (
    "libldb2:amd64",
    "2:2.6.2+samba4.17.12+dfsg-0+deb12u1",
    "samba",
    "2:4.17.12+dfsg-0+deb12u1",
    DEB,
)
KERNEL_RUN = (
    "linux-image-6.1.0-25-amd64",
    "6.1.106-3",
    "linux-signed-amd64",
    "6.1.106-3",
    DEB,
)
KERNEL_OLD = (
    "linux-image-6.1.0-18-amd64",
    "6.1.76-1",
    "linux-signed-amd64",
    "6.1.76-1",
    DEB,
)
IMAGEMAGICK = (
    "imagemagick",
    "8:6.9.11.60+dfsg-1.6+deb12u1",
    "imagemagick",
    "8:6.9.11.60+dfsg-1.6+deb12u1",
    DEB,
)
DOCKER = (
    "docker-ce",
    "5:27.3.1-1~debian.12~bookworm",
    "docker-ce",
    "5:27.3.1-1~debian.12~bookworm",
    "Docker",
)
POSTGRES = ("postgresql-15", "15.6-0+deb12u1", "postgresql-15", "15.6-0+deb12u1", DEB)
LOCAL_TOOL = ("ocs-local-tool", "1.0", "ocs-local-tool", "1.0", "")
UBU = "Ubuntu"
CURL_BIONIC = ("curl", "7.58.0-2ubuntu3.24", "curl", "7.58.0-2ubuntu3.24", UBU)
SSL_BIONIC = (
    "libssl1.1:amd64",
    "1.1.1-1ubuntu2.1~18.04.23",
    "openssl",
    "1.1.1-1ubuntu2.1~18.04.23",
    UBU,
)
KERNEL_BIONIC = (
    "linux-image-4.15.0-213-generic",
    "4.15.0-213.224",
    "linux",
    "4.15.0-213.224",
    UBU,
)
CURL_NOBLE = ("curl", "8.5.0-2ubuntu10.13", "curl", "8.5.0-2ubuntu10.13", UBU)
KERNEL_NOBLE = (
    "linux-image-6.8.0-45-generic",
    "6.8.0-45.45",
    "linux",
    "6.8.0-45.45",
    UBU,
)
FIREFOX_NOBLE = ("firefox", "1:1snap1-0ubuntu5", "firefox", "1:1snap1-0ubuntu5", UBU)
ROCKY = "Rocky Enterprise Software Foundation"
ACL_ROCKY = ("acl", "2.3.1-3.el9", "acl", "2.3.1-3.el9", ROCKY)
SSL_ROCKY = ("openssl", "1:3.0.7-27.el9", "openssl", "1:3.0.7-27.el9", ROCKY)
KERNEL_EL9 = "5.14.0-427.13.1.el9_4"
KERNEL_ROCKY = ("kernel-core", KERNEL_EL9, "kernel", KERNEL_EL9, ROCKY)
EPEL_TOOL = ("epel-tool", "2.0-1.el9", "epel-tool", "2.0-1.el9", "Fedora Project")
SSL_ALMA = ("openssl", "1:3.0.7-27.el9", "openssl", "1:3.0.7-27.el9", "AlmaLinux")
KERNEL_ALMA = ("kernel-core", KERNEL_EL9, "kernel", KERNEL_EL9, "AlmaLinux")

WEB_BEFORE = [CURL_NEW, OPENSSL_12, APACHE, LIBLDB, KERNEL_RUN, KERNEL_OLD]
PACKAGES = {
    "srv-web-01": (
        WEB_BEFORE + [IMAGEMAGICK, DOCKER],
        WEB_BEFORE + [DOCKER, LOCAL_TOOL],
    ),
    "srv-db-01": (
        [CURL_OLD, OPENSSL_12, POSTGRES, KERNEL_RUN],
        [CURL_NEW, OPENSSL_12, POSTGRES, KERNEL_RUN],
    ),
    "ubuntu-legacy-01": ([CURL_BIONIC, SSL_BIONIC, KERNEL_BIONIC], None),
    "ubuntu-desk-01": ([CURL_NOBLE, KERNEL_NOBLE, FIREFOX_NOBLE], None),
    "rocky-app-01": ([ACL_ROCKY, SSL_ROCKY, EPEL_TOOL, KERNEL_ROCKY], None),
    "alma-app-01": ([SSL_ALMA, KERNEL_ALMA], None),
    # Runs its host's kernel: no installed package is the running kernel
    "container-01": ([CURL_NEW, OPENSSL_12, KERNEL_RUN], None),
    "lab-01": ([CURL_OLD, OPENSSL_12, APACHE, KERNEL_RUN], None),
}

# Windows and macOS: (name, publisher, version, CPE product or None for review)
APPS = {
    "win-pc-01": [
        ("Zoom Workplace", "Zoom Video Communications, Inc.", "6.1.5", "zoom:zoom"),
        (
            "Microsoft Edge",
            "Microsoft Corporation",
            "130.0.2849.56",
            "microsoft:edge_chromium",
        ),
        ("7-Zip 23.01 (x64)", "Igor Pavlov", "23.01", "7-zip:7-zip"),
        ("Notepad++ (64-bit x64)", "Notepad++ Team", "8.6.4", None),
    ],
    "mac-01": [
        ("Firefox", "Mozilla", "128.0", "mozilla:firefox"),
        ("Tunnelblick", "Tunnelblick", "6.0", "tunnelblick:tunnelblick"),
    ],
}
# Ten days ago Edge was identified as EdgeHTML (microsoft:edge)
EDGE_BEFORE = "microsoft:edge"


def fixed_in(version):
    return [[{"introduced": "0"}, {"fixed": version}]]


UNFIXED = [[{"introduced": "0"}]]
V31_CRITICAL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
V31_HIGH = "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H"
V31_MEDIUM = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"
V31_LOW = "CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:L/I:N/A:N"

# OSV detection advisories: (id, source, CVEs, summary, vector, rating,
# [(ecosystem, package, ranges, urgency)])
ADVISORIES = [
    (
        "DEBIAN-CVE-2026-90001",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90001"],
        "curl: heap overflow in the SOCKS5 proxy handshake (demo)",
        V31_CRITICAL,
        "",
        [("Debian:12", "curl", fixed_in("7.88.1-10+deb12u8"), "high")],
    ),
    (
        "DEBIAN-CVE-2026-90002",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90002"],
        "curl: cookie leak on cross-origin redirect (demo)",
        V31_LOW,
        "",
        [("Debian:12", "curl", UNFIXED, "unimportant")],
    ),
    (
        "DEBIAN-CVE-2026-90003",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90003"],
        "OpenSSL: timing side channel in RSA decryption (demo)",
        V31_MEDIUM,
        "",
        [("Debian:12", "openssl", fixed_in("3.0.15-1~deb12u1"), "medium")],
    ),
    (
        "DEBIAN-CVE-2026-90004",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90004"],
        "Apache HTTP Server: request smuggling with mod_proxy (demo)",
        V31_HIGH,
        "",
        [("Debian:12", "apache2", fixed_in("2.4.65-1~deb12u1"), "not yet assigned")],
    ),
    (
        "DEBIAN-CVE-2026-90005",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90005"],
        "Samba: authentication bypass in the AD DC (demo)",
        V31_CRITICAL,
        "",
        [("Debian:12", "samba", fixed_in("2:4.17.12+dfsg-0+deb12u2"), "high")],
    ),
    (
        "DEBIAN-CVE-2026-90006",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90006"],
        "Linux kernel: use after free in netfilter (demo)",
        V31_HIGH,
        "",
        [("Debian:12", "linux", fixed_in("6.1.112-1"), "high")],
    ),
    (
        "DEBIAN-CVE-2026-90007",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90007"],
        "ImageMagick: out of bounds read in the PSD decoder (demo)",
        V31_MEDIUM,
        "",
        [("Debian:12", "imagemagick", UNFIXED, "low")],
    ),
    (
        "DEBIAN-CVE-2026-90008",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90008"],
        "PostgreSQL: SQL injection in pg_dump (demo)",
        V31_HIGH,
        "",
        [("Debian:12", "postgresql-15", fixed_in("15.8-0+deb12u1"), "medium")],
    ),
    (
        "DEBIAN-CVE-2026-90009",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90009"],
        "curl: advisory withdrawn by Debian (demo)",
        V31_MEDIUM,
        "",
        [("Debian:12", "curl", UNFIXED, "medium")],
    ),
    (
        "UBUNTU-CVE-2026-90101",
        SOURCE_OSV_UBUNTU,
        ["CVE-2026-90101"],
        "curl: HSTS bypass with IDN host names (demo)",
        V31_HIGH,
        "medium",
        [
            ("Ubuntu:18.04:LTS", "curl", UNFIXED, ""),
            ("Ubuntu:Pro:18.04:LTS", "curl", fixed_in("7.58.0-2ubuntu3.24+esm6"), ""),
            ("Ubuntu:24.04:LTS", "curl", fixed_in("8.5.0-2ubuntu10.15"), ""),
        ],
    ),
    (
        "UBUNTU-CVE-2026-90102",
        SOURCE_OSV_UBUNTU,
        ["CVE-2026-90102"],
        "OpenSSL: NULL dereference in PKCS12 parsing (demo)",
        V31_MEDIUM,
        "low",
        [
            ("Ubuntu:18.04:LTS", "openssl", UNFIXED, ""),
            ("Ubuntu:Pro:18.04:LTS", "openssl", UNFIXED, ""),
        ],
    ),
    (
        "UBUNTU-CVE-2026-90103",
        SOURCE_OSV_UBUNTU,
        ["CVE-2026-90103"],
        "Linux kernel: race in the io_uring subsystem (demo)",
        V31_HIGH,
        "medium",
        [("Ubuntu:24.04:LTS", "linux", UNFIXED, "")],
    ),
    (
        "UBUNTU-CVE-2026-90104",
        SOURCE_OSV_UBUNTU,
        ["CVE-2026-90104"],
        "Linux kernel: information leak in the Bluetooth stack (demo)",
        V31_LOW,
        "low",
        [("Ubuntu:24.04:LTS", "linux", UNFIXED, "")],
    ),
    (
        "UBUNTU-CVE-2026-90105",
        SOURCE_OSV_UBUNTU,
        ["CVE-2026-90105"],
        "Linux kernel: privilege escalation in overlayfs (demo)",
        V31_CRITICAL,
        "high",
        [("Ubuntu:24.04:LTS", "linux", fixed_in("6.8.0-48.48"), "")],
    ),
    (
        "RLSA-2026:90201",
        SOURCE_OSV_ROCKY,
        ["CVE-2026-90201", "CVE-2026-90202"],
        "Important: acl security update (demo)",
        V31_HIGH,
        "Important",
        [("Rocky Linux:9", "acl", fixed_in("0:2.3.1-4.el9"), "")],
    ),
    (
        "RLSA-2026:90203",
        SOURCE_OSV_ROCKY,
        ["CVE-2026-90003"],
        "Moderate: openssl security update (demo)",
        V31_MEDIUM,
        "Moderate",
        [("Rocky Linux:9", "openssl", fixed_in("1:3.0.7-28.el9_4"), "")],
    ),
]
# Reference advisories (DSA, USN): listed with their CVEs, no packages
REFERENCES = [
    (
        "DSA-9001-1",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90001"],
        "curl security update (demo)",
    ),
    (
        "DLA-9002-1",
        SOURCE_OSV_DEBIAN,
        ["CVE-2026-90005"],
        "samba security update (demo)",
    ),
    ("USN-9101-1", SOURCE_OSV_UBUNTU, ["CVE-2026-90101"], "curl vulnerability (demo)"),
]

# NVD CVEs: (id, description, vector, score, [(criteria, bounds, conditional)])
NVD = [
    (
        "CVE-2026-90301",
        "Zoom Workplace: improper input validation in the chat (demo)",
        V31_HIGH,
        8.8,
        [
            (
                "cpe:2.3:a:zoom:meetings:*:*:*:*:*:*:*:*",
                {"versionEndExcluding": "6.2.0"},
                False,
            )
        ],
    ),
    (
        "CVE-2026-90302",
        "Zoom Workplace: weakness on macOS only (demo)",
        V31_MEDIUM,
        6.5,
        [
            (
                "cpe:2.3:a:zoom:zoom:*:*:*:*:*:*:*:*",
                {"versionEndExcluding": "6.3.0"},
                True,
            )
        ],
    ),
    (
        "CVE-2026-90303",
        "Microsoft Edge (Chromium-based): type confusion in V8 (demo)",
        V31_HIGH,
        8.8,
        [
            (
                "cpe:2.3:a:microsoft:edge_chromium:*:*:*:*:*:*:*:*",
                {"versionEndExcluding": "131.0.2903.48"},
                False,
            )
        ],
    ),
    (
        "CVE-2026-90304",
        "Microsoft Edge (EdgeHTML): memory corruption (demo)",
        V31_HIGH,
        7.5,
        [("cpe:2.3:a:microsoft:edge:*:*:*:*:*:*:*:*", {}, False)],
    ),
    (
        "CVE-2026-90305",
        "7-Zip: directory traversal in archive extraction (demo)",
        V31_HIGH,
        7.8,
        [("cpe:2.3:a:7-zip:7-zip:*:*:*:*:*:*:*:*", {}, False)],
    ),
    (
        "CVE-2026-90306",
        "Firefox: use after free in the layout engine (demo)",
        V31_CRITICAL,
        9.8,
        [
            (
                "cpe:2.3:a:mozilla:firefox:*:*:*:*:*:*:*:*",
                {"versionEndExcluding": "131.0"},
                False,
            )
        ],
    ),
    (
        "CVE-2026-90307",
        "Tunnelblick: local file read through a symlink (demo)",
        V31_MEDIUM,
        5.5,
        [
            (
                "cpe:2.3:a:tunnelblick:tunnelblick:*:*:*:*:*:*:*:*",
                {"versionStartIncluding": "3.5.3", "versionEndExcluding": "8.0.1"},
                False,
            )
        ],
    ),
    (
        "CVE-2023-90308",
        "7-Zip: heap overflow in the RAR decoder (demo, old year)",
        V31_HIGH,
        7.8,
        [
            (
                "cpe:2.3:a:7-zip:7-zip:*:*:*:*:*:*:*:*",
                {"versionEndExcluding": "24.0"},
                False,
            )
        ],
    ),
]
KEV = {"CVE-2026-90001": date(2026, 10, 20), "CVE-2026-90303": date(2026, 10, 28)}
EPSS = {
    "CVE-2026-90001": (0.94, 0.999),
    "CVE-2026-90003": (0.02, 0.61),
    "CVE-2026-90004": (0.37, 0.97),
    "CVE-2026-90005": (0.71, 0.99),
    "CVE-2026-90006": (0.05, 0.82),
    "CVE-2026-90101": (0.12, 0.91),
    "CVE-2026-90105": (0.33, 0.96),
    "CVE-2026-90201": (0.01, 0.3),
    "CVE-2026-90301": (0.08, 0.88),
    "CVE-2026-90303": (0.62, 0.99),
    "CVE-2026-90306": (0.21, 0.94),
}


def _advisory_ids():
    return [a[0] for a in ADVISORIES] + [r[0] for r in REFERENCES]


def _cve_ids():
    ids = {cve for a in ADVISORIES for cve in a[2]} | {n[0] for n in NVD}
    return sorted(ids)


class Command(BaseCommand):
    help = "Create (or remove with --reset) demo data for the vulnerability screens"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Only remove the demo data"
        )

    def handle(self, *args, **options):
        self.remove()
        if options["reset"]:
            self.stdout.write("Demo data removed")
            return
        now = timezone.now()
        before = now - timedelta(days=10)
        self.create_data()
        assets = self.create_machines()
        self.install(assets, before=True)
        self.set_sources(before)
        years = security_config.current().nvd_years
        # Ten days ago the NVD window reached 2023: its CVE closes now
        self.set_nvd_years(4)
        try:
            ScanService.run(now=before)
        finally:
            self.set_nvd_years(years)
        # What changed since: upgrades, an uninstall, Edge's identity, an
        # advisory withdrawn, fresh data
        self.install(assets, before=False)
        OsvAdvisory.objects.filter(advisory_id="DEBIAN-CVE-2026-90009").update(
            withdrawn=True
        )
        self.set_sources(now)
        counts = ScanService.run(now=now)
        self.create_exclusions(assets, now)
        self.stdout.write(f"Demo data created: {len(assets)} machines, scan {counts}")

    # Removal

    def remove(self):
        with transaction.atomic():
            assets = InventoryBase.objects.filter(uuid__startswith=PREFIX)
            entry_ids = list(
                SoftwareDictionary.objects.filter(assets__in=assets).values_list(
                    "id", flat=True
                )
            )
            Exclusion.objects.filter(asset__in=assets).delete()
            AssetGroup.objects.filter(name=GROUP).delete()
            assets.delete()
            SoftwareDictionary.objects.filter(
                id__in=entry_ids, assets__isnull=True
            ).delete()
            OsvAdvisory.objects.filter(advisory_id__in=_advisory_ids()).delete()
            NvdCve.objects.filter(cve_id__in=_cve_ids()).delete()
            KevEntry.objects.filter(cve__in=_cve_ids()).delete()
            EpssScore.objects.filter(cve__in=_cve_ids()).delete()
            Vulnerability.objects.filter(vuln_id__in=_cve_ids()).delete()
            # A cache, computed again by the next scan: evaluations made with
            # demo data must not stay
            Evaluation.objects.all().delete()
            # The demo writes source states: they say "never loaded" until
            # the next synchronization
            SourceSync.objects.all().delete()

    # Source data

    def create_data(self):
        for advisory_id, source, cves, summary, vector, rating, rows in ADVISORIES:
            advisory = OsvAdvisory.objects.create(
                source=source,
                advisory_id=advisory_id,
                cves=cves,
                summary=summary,
                published=timezone.now() - timedelta(days=30),
                modified="demo",
                cvss_vector=vector,
                rating=rating,
            )
            for cve in cves:
                OsvAdvisoryCve.objects.create(advisory=advisory, cve=cve)
            for ecosystem, package, ranges, urgency in rows:
                OsvAffected.objects.create(
                    advisory=advisory,
                    ecosystem=ecosystem,
                    package=package,
                    ranges=ranges,
                    urgency=urgency,
                )
        for advisory_id, source, cves, summary in REFERENCES:
            advisory = OsvAdvisory.objects.create(
                source=source,
                advisory_id=advisory_id,
                cves=cves,
                summary=summary,
                detection=False,
                modified="demo",
            )
            for cve in cves:
                OsvAdvisoryCve.objects.create(advisory=advisory, cve=cve)
        for cve_id, description, vector, score, matches in NVD:
            cve = NvdCve.objects.create(
                cve_id=cve_id,
                year=int(cve_id.split("-")[1]),
                published=timezone.now() - timedelta(days=20),
                modified=timezone.now() - timedelta(days=5),
                description=description,
                cvss3_vector=vector,
                cvss3_score=score,
            )
            for criteria, bounds, conditional in matches:
                NvdMatch.objects.create(
                    cve=cve,
                    vendor_product=":".join(criteria.split(":")[3:5]),
                    criteria=criteria,
                    bounds=bounds,
                    conditional=conditional,
                )
        for cve, added in KEV.items():
            KevEntry.objects.create(cve=cve, date_added=added)
        for cve, (score, percentile) in EPSS.items():
            EpssScore.objects.create(cve=cve, score=score, percentile=percentile)

    def set_sources(self, when):
        """Debian, Ubuntu, NVD, KEV, EPSS fresh; Rocky stale; Alma never loaded."""
        ecosystems = {
            SOURCE_OSV_DEBIAN: ["Debian:11", "Debian:12", "Debian:13"],
            SOURCE_OSV_UBUNTU: [
                "Ubuntu:18.04:LTS",
                "Ubuntu:Pro:18.04:LTS",
                "Ubuntu:22.04:LTS",
                "Ubuntu:24.04:LTS",
                "Ubuntu:Pro:24.04:LTS",
            ],
            SOURCE_OSV_ROCKY: ["Rocky Linux:8", "Rocky Linux:9"],
        }
        for source in (
            SOURCE_OSV_DEBIAN,
            SOURCE_OSV_UBUNTU,
            SOURCE_NVD,
            SOURCE_KEV,
            SOURCE_EPSS,
        ):
            details = {"ecosystems": ecosystems.get(source, [])}
            if source == SOURCE_NVD:
                details = {"window": [when.year - 2, when.year - 1, when.year]}
            SourceSync.objects.update_or_create(
                source=source,
                defaults={
                    "last_attempt": when,
                    "last_success": when,
                    "data_changed_at": when,
                    "error": "",
                    "record_count": 1000,
                    "details": details,
                },
            )
        SourceSync.objects.update_or_create(
            source=SOURCE_OSV_ROCKY,
            defaults={
                "last_attempt": when,
                "last_success": when - timedelta(hours=60),
                "data_changed_at": when - timedelta(hours=60),
                "error": "HTTPSConnectionPool: Read timed out (demo)",
                "record_count": 800,
                "details": {"ecosystems": ecosystems[SOURCE_OSV_ROCKY]},
            },
        )
        SourceSync.objects.update_or_create(
            source=SOURCE_OSV_ALMA,
            defaults={
                "last_attempt": when,
                "last_success": None,
                "data_changed_at": None,
                "error": "404 Not Found (demo)",
                "record_count": 0,
                "details": {},
            },
        )

    @staticmethod
    def set_nvd_years(years):
        section = Config.objects.filter(name=security_config.SECTION).first()
        if section is None:
            return
        section.value = [
            {**item, "value": years} if item.get("name") == "nvd_years" else item
            for item in section.value
        ]
        section.save()

    # Machines and software

    def create_machines(self):
        assets = {}
        for name, family, key, (os_id, like, release, codename), running in MACHINES:
            asset = InventoryBase.objects.create(
                name=name,
                description="Vulnerability demo machine",
                serial=f"SER-{name}",
                osname=os_id,
                osversion=release,
                uuid=f"{PREFIX}{name}",
                domain="demo.local",
                agent="OCS-NG_demo",
            )
            AssetPlatform.objects.create(
                asset=asset,
                os_id=os_id,
                os_like=like,
                os_release=release,
                os_codename=codename,
                running_kernel=running,
                family=family,
                key=key,
            )
            assets[name] = asset
        return assets

    def install(self, assets, before):
        normalizers = build_normalizers(None, {}, IdentityService.known_origins())
        for name, (packages_before, packages_now) in PACKAGES.items():
            asset = assets[name]
            packages = packages_before if before else (packages_now or packages_before)
            asset.software_dictionary_entries.clear()
            platform = asset.platform
            for package, version, source, source_version, origin in packages:
                entry = self.entry(
                    asset,
                    name=package,
                    version=version,
                    platform_family=platform.family,
                    platform_key=platform.key,
                    architecture="amd64" if platform.family == "deb" else "x86_64",
                    package_format=platform.family,
                    source_package=source,
                    source_version=source_version,
                    package_origin=origin,
                )
                result = IdentityService._normalize(entry, normalizers, None)
                IdentityService._save(entry, result, 0)
        for name, apps in APPS.items():
            asset = assets[name]
            asset.software_dictionary_entries.clear()
            family = asset.platform.family
            for app, publisher, version, product in apps:
                entry = self.entry(
                    asset,
                    name=app,
                    publisher=publisher,
                    version=version,
                    platform_family=family,
                    platform_key=family,
                )
                if before and product == "microsoft:edge_chromium":
                    product = EDGE_BEFORE
                self.identify_application(entry, family, product)

    @staticmethod
    def entry(asset, **values):
        entry, _ = SoftwareDictionary.objects.get_or_create(**values)
        entry.assets.add(asset)
        SoftwareDictionary.objects.filter(pk=entry.pk).update(
            installation_number=entry.assets.count()
        )
        return entry

    @staticmethod
    def identify_application(entry, family, product):
        from inventory.software_identity.match_key import match_key

        key = match_key(entry.name)
        if product is None:
            values = {
                "status": "review",
                "score": 0.72,
                "candidates": [
                    {"product": "notepad-plus-plus:notepad++", "score": 0.72},
                    {"product": "notepad\\+\\+:notepad\\+\\+", "score": 0.66},
                ],
                "scheme": "",
                "product": "",
                "identifier": "",
            }
        else:
            values = {
                "status": "matched",
                "score": 0.97,
                "candidates": [{"product": product, "score": 0.97}],
                "scheme": "cpe",
                "product": product,
                "identifier": cpe_identifier(product, cpe_version(entry.version)),
            }
        SoftwareIdentity.objects.update_or_create(
            entry=entry,
            defaults={
                "family": family,
                "match_key": key,
                "reason": "",
                "version": cpe_version(entry.version),
                **values,
            },
        )

    # Exclusions

    def create_exclusions(self, assets, now):
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if user is None:
            self.stdout.write("No superuser: exclusions skipped")
            return
        group = AssetGroup.objects.create(
            name=GROUP,
            description="Machines left out of the vulnerability scan (demo)",
            user=user,
            visibility="public",
        )
        group.assets.add(assets["lab-01"])
        Exclusion.objects.create(
            group=group,
            comment="Lab machines, rebuilt every week (demo)",
            user=user,
        )
        Exclusion.objects.create(
            asset=assets["srv-web-01"],
            vuln_id="CVE-2026-90004",
            comment="mod_proxy disabled on this server (demo)",
            expires_at=now + timedelta(days=30),
            user=user,
        )
        Exclusion.objects.create(
            asset=assets["srv-db-01"],
            vuln_id="CVE-2026-90008",
            comment="Expired risk acceptance (demo)",
            expires_at=now - timedelta(days=2),
            user=user,
        )
