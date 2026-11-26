import io
import json
import re
import tarfile

import pytest

# (part, vendor, product, version, English title, deprecated)
FIXTURE_CPES = [
    ("a", "mozilla", "firefox", "154.0.1", "Mozilla Firefox 154.0.1", False),
    ("a", "mozilla", "firefox", "150.0", "Mozilla Firefox 150.0", False),
    ("a", "mozilla", "firefox_esr", "115.0", "Mozilla Firefox ESR 115.0", False),
    (
        "a",
        "microsoft",
        "edge",
        "44.19041.1266.0",
        "Microsoft Edge 44.19041.1266.0",
        False,
    ),
    ("a", "microsoft", "edge", "97.0.4692.99", "Microsoft Edge 97.0.4692.99", False),
    (
        "a",
        "microsoft",
        "edge_chromium",
        "152.0.4191.66",
        "Microsoft Edge Chromium 152.0.4191.66",
        False,
    ),
    (
        "a",
        "microsoft",
        "visual_studio_2026",
        "18.9.2",
        "Microsoft Visual Studio 2026 18.9.2",
        False,
    ),
    (
        "a",
        "microsoft",
        "visual_studio_community",
        "16.0",
        "Microsoft Visual Studio Community 2019 16.0",
        False,
    ),
    (
        "a",
        "notepad-plus-plus",
        "notepad++",
        "8.9.6.4",
        "Notepad-plus-plus Notepad++ 8.9.6.4",
        False,
    ),
    ("a", "microsoft", "visual_c++", "2010", "Microsoft Visual C++ 2010", False),
    ("a", "apple", "pages", "13.1", "Apple Pages 13.1", False),
    ("a", "7-zip", "7-zip", "24.08", "7-Zip 24.08", False),
    ("a", "info-zip", "zip", "3.0", "Info-ZIP Zip 3.0", False),
    ("a", "synology", "contacts", "1.0", "Synology Contacts 1.0", False),
    ("a", "git-scm", "git", "2.45.0", "Git-scm Git 2.45.0", False),
    ("a", "oldvendor", "oldproduct", "1.0", "Oldvendor Oldproduct 1.0", True),
    ("o", "microsoft", "windows_11", "-", "Microsoft Windows 11", False),
]

_CPE_SPECIAL = re.compile(r"([^A-Za-z0-9_.\-])")


def _escape(value):
    return _CPE_SPECIAL.sub(r"\\\1", value)


def build_feed(cpes=FIXTURE_CPES):
    """NVD CPE 2.0 feed (tar.gz of JSON chunks) holding the given CPE names."""
    products = [
        {
            "cpe": {
                "cpeName": (
                    f"cpe:2.3:{part}:{_escape(vendor)}:{_escape(product)}"
                    f":{_escape(version)}:*:*:*:*:*:*:*"
                ),
                "deprecated": deprecated,
                "titles": [{"title": title, "lang": "en"}],
            }
        }
        for part, vendor, product, version, title, deprecated in cpes
    ]
    data = json.dumps({"products": products}).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("nvdcpe-2.0-chunks/nvdcpe-2.0-chunk-00001.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def fake_open(feed, sha="0" * 64):
    def _open(url):
        if url.endswith(".meta"):
            return io.BytesIO(
                "lastModifiedDate:2026-10-06T23:50:00-04:00\r\n"
                f"sha256:{sha}\r\n".encode()
            )
        return io.BytesIO(feed)

    return _open


@pytest.fixture
def cpe_index(db):
    from inventory.software_identity.cpe.sync import sync_cpe_index

    sync_cpe_index(open_url=fake_open(build_feed()))
