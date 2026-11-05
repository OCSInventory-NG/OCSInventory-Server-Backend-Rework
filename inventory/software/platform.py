"""
Platform of an asset, resolved from the OS values its software mapping points
to: os-release fields on Linux, OS name and version on Windows and macOS, the
OS name and version of the HARDWARE section for Legacy agents.

Pure: the Debian family releases ({(base, codename): version}, from
DistroRelease) are passed in by the caller.
"""

import re
from dataclasses import dataclass

MACOS_PREFIXES = ("macos", "mac os x", "os x")
RPM_IDS = ("rhel", "centos", "fedora", "rocky", "almalinux")
_NUMBER = re.compile(r"\d+(\.\d+)*")


@dataclass(frozen=True)
class Platform:
    family: str = ""
    key: str = ""


def _clean(value):
    return (value or "").strip().strip("\"'").strip().lower()


def resolve(os_id, os_like, os_release, os_codename, releases):
    os_id, os_like, release, codename = (
        _clean(value) for value in (os_id, os_like, os_release, os_codename)
    )
    if "windows" in os_id:
        return Platform("windows", "windows")
    if os_id.startswith(MACOS_PREFIXES):
        return Platform("macos", "macos")
    if " " in os_id:
        # Legacy agents send a name ("Ubuntu 20.04"), not an os-release id.
        # Extract the base name and version number if present.
        number = _NUMBER.search(os_id)
        os_id = os_id.split()[0]
        release = number.group(0) if number else ""

    like = os_like.split()
    bases = {base for base, _ in releases}
    if os_id in bases:
        return _debian_family(os_id, release, codename, releases)
    base = next((word for word in like if word in bases), None)
    if base:
        # A derivative's own version means nothing to its base: use the codename
        return _debian_family(base, "", codename, releases)
    if os_id in RPM_IDS or any(word in RPM_IDS for word in like):
        major = release.split(".")[0]
        return Platform("rpm", f"{os_id}:{major}" if major else "")
    return Platform()


def _debian_family(base, release, codename, releases):
    if not release:
        release = releases.get((base, codename), "")
    for version in {v for (b, _), v in releases.items() if b == base}:
        if release.startswith(version + "."):
            release = version
            break
    return Platform("deb", f"{base}:{release}" if release else "")
