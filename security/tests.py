import pytest
from django.db import IntegrityError
from security.cvss import base_score, level
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
