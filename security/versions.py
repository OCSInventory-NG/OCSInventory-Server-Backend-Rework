"""
Package version comparison as the package managers do it, so that OCS decides
itself whether an installed version is before a fix.

dpkg: epoch, upstream version and Debian revision, compared with the dpkg
algorithm ("~" sorts before anything, even the end). rpm: epoch, version and
release, compared with rpmvercmp ("~" before anything, "^" after the end).
"""

import re
from functools import cmp_to_key

_DIGITS = "0123456789"


def _dpkg_order(char):
    if not char:
        return 0
    if char in _DIGITS:
        return 0
    if char.isascii() and char.isalpha():
        return ord(char)
    if char == "~":
        return -1
    return ord(char) + 256


def _verrevcmp(a, b):
    i = j = 0
    la, lb = len(a), len(b)
    while i < la or j < lb:
        first_diff = 0
        while (i < la and a[i] not in _DIGITS) or (j < lb and b[j] not in _DIGITS):
            ac = _dpkg_order(a[i] if i < la else "")
            bc = _dpkg_order(b[j] if j < lb else "")
            if ac != bc:
                return ac - bc
            i += 1
            j += 1
        while i < la and a[i] == "0":
            i += 1
        while j < lb and b[j] == "0":
            j += 1
        while i < la and a[i] in _DIGITS and j < lb and b[j] in _DIGITS:
            if not first_diff:
                first_diff = ord(a[i]) - ord(b[j])
            i += 1
            j += 1
        if i < la and a[i] in _DIGITS:
            return 1
        if j < lb and b[j] in _DIGITS:
            return -1
        if first_diff:
            return first_diff
    return 0


def _epoch(version):
    epoch, sep, rest = version.partition(":")
    if sep and epoch.isdigit():
        return int(epoch), rest
    return 0, version


def _last_dash(text):
    """(before, after) the last "-", (text, "") without one."""
    before, sep, after = text.rpartition("-")
    return (before, after) if sep else (text, "")


def _sign(value):
    return (value > 0) - (value < 0)


def dpkg_compare(a, b):
    """-1, 0 or 1 as dpkg --compare-versions orders a and b."""
    a, b = (a or "").strip(), (b or "").strip()
    epoch_a, rest_a = _epoch(a)
    epoch_b, rest_b = _epoch(b)
    if epoch_a != epoch_b:
        return _sign(epoch_a - epoch_b)
    upstream_a, revision_a = _last_dash(rest_a)
    upstream_b, revision_b = _last_dash(rest_b)
    result = _verrevcmp(upstream_a, upstream_b)
    if result:
        return _sign(result)
    return _sign(_verrevcmp(revision_a, revision_b))


def _rpm_char(text, index):
    return text[index] if index < len(text) else ""


def rpmvercmp(a, b):
    """-1, 0 or 1 as rpm orders two version (or release) strings."""
    if a == b:
        return 0
    i = j = 0
    la, lb = len(a), len(b)
    while i < la or j < lb:
        while i < la and not a[i].isalnum() and a[i] not in "~^":
            i += 1
        while j < lb and not b[j].isalnum() and b[j] not in "~^":
            j += 1
        ca, cb = _rpm_char(a, i), _rpm_char(b, j)
        if ca == "~" or cb == "~":
            if ca != "~":
                return 1
            if cb != "~":
                return -1
            i += 1
            j += 1
            continue
        if ca == "^" or cb == "^":
            if not ca:
                return -1
            if not cb:
                return 1
            if ca != "^":
                return 1
            if cb != "^":
                return -1
            i += 1
            j += 1
            continue
        if not (i < la and j < lb):
            break
        start_a, start_b = i, j
        if a[i] in _DIGITS:
            while i < la and a[i] in _DIGITS:
                i += 1
            while j < lb and b[j] in _DIGITS:
                j += 1
            numeric = True
        else:
            while i < la and a[i].isascii() and a[i].isalpha():
                i += 1
            while j < lb and b[j].isascii() and b[j].isalpha():
                j += 1
            numeric = False
        segment_a, segment_b = a[start_a:i], b[start_b:j]
        if not segment_b:
            return 1 if numeric else -1
        if numeric:
            segment_a = segment_a.lstrip("0")
            segment_b = segment_b.lstrip("0")
            if len(segment_a) != len(segment_b):
                return 1 if len(segment_a) > len(segment_b) else -1
        if segment_a != segment_b:
            return 1 if segment_a > segment_b else -1
    if i >= la and j >= lb:
        return 0
    return -1 if i >= la else 1


def rpm_compare(a, b):
    """-1, 0 or 1 for two [epoch:]version[-release] strings, as rpm orders them."""
    a, b = (a or "").strip(), (b or "").strip()
    epoch_a, rest_a = _epoch(a)
    epoch_b, rest_b = _epoch(b)
    if epoch_a != epoch_b:
        return _sign(epoch_a - epoch_b)
    version_a, release_a = _last_dash(rest_a)
    version_b, release_b = _last_dash(rest_b)
    result = rpmvercmp(version_a, version_b)
    if result or not release_a or not release_b:
        # A version without release matches every release of that version
        return result
    return rpmvercmp(release_a, release_b)


def comparator(ecosystem):
    """The comparison of an OSV ecosystem's versions, None when not handled."""
    base = (ecosystem or "").split(":")[0]
    if base in ("Debian", "Ubuntu"):
        return dpkg_compare
    if base in ("Rocky Linux", "AlmaLinux", "Red Hat"):
        return rpm_compare
    return None


def sort_key(compare):
    return cmp_to_key(compare)


# RPM modules. A module build carries ".module+el8.5.0+721+4c107270" (Alma:
# "module_el8"), not its stream: the advisories name it in their summary
# ("nodejs:16 security update", "virt:rhel and virt-devel:rhel ...").
_MODULE_BUILD = re.compile(r"\.module[+_]el\d")
_MODULE_STREAM = re.compile(r"(?<![\w.+-])([A-Za-z0-9][\w.+-]*):([A-Za-z0-9][\w.+-]*)")


def is_module_build(version):
    return bool(_MODULE_BUILD.search(version or ""))


def module_streams(summary):
    """{module: stream} named by an advisory's summary."""
    return dict(_MODULE_STREAM.findall(summary or ""))


def same_stream(installed, fixed, package, streams):
    """
    Whether a fix can apply to the installed version: a module build is only
    fixed by a build of the same module stream, a package outside modules by
    a package outside modules. A numbered stream of the package's own module
    (nodejs:16, postgresql:13) holds its upstream versions (16.x, 13.x); a
    stream without a number (virt:rhel) cannot be told from the version.
    """
    module_fix = (fixed and is_module_build(fixed)) or package in streams
    if bool(module_fix) != is_module_build(installed):
        return False
    stream = streams.get(package, "")
    if not is_module_build(installed) or not stream[:1].isdigit():
        return True
    version, _ = _last_dash(_epoch(installed)[1])
    return version == stream or version.startswith(stream + ".")
