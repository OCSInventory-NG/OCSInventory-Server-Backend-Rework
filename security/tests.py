import pytest
from django.db import IntegrityError
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
