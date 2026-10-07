from urllib.parse import quote

from .base import MATCHED, UNSUPPORTED, IdentityResult


class LinuxNormalizer:
    """Distribution packages: a purl built from the source package and the platform."""

    def __init__(self, family):
        self.family = family

    def normalize(self, record):
        source = record.source_package or record.name.split(":")[0]
        key = source.lower()
        if record.package_format and record.package_format.lower() != self.family:
            return IdentityResult(UNSUPPORTED, key, reason="package_format")
        if not record.platform_key:
            return IdentityResult(UNSUPPORTED, key, reason="unknown_release")

        distro, release = record.platform_key.split(":", 1)
        # purl: rpm names are case sensitive, deb names are lowercase
        name = source if self.family == "rpm" else key
        product = f"pkg:{self.family}/{distro}/{quote(name, safe='')}"
        version = record.version
        qualifiers = {"distro": f"{distro}-{release}"}
        if record.architecture:
            qualifiers["arch"] = record.architecture.lower()
        if self.family == "rpm" and ":" in version:
            # purl rpm type: the epoch is a qualifier, not part of the version
            qualifiers["epoch"], version = version.split(":", 1)
        query = "&".join(
            f"{name}={quote(value, safe='')}"
            for name, value in sorted(qualifiers.items())
        )
        at_version = f"@{quote(version, safe='')}" if version else ""

        return IdentityResult(
            MATCHED,
            key,
            reason="" if record.source_package else "source_not_mapped",
            scheme="purl",
            identifier=f"{product}{at_version}?{query}",
            product=product,
            version=record.version,
        )
