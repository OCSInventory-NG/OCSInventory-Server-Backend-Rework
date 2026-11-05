"""
Kernel packages: only the running kernel is checked. Installed but not running
kernels made 70% of the fixable vulnerabilities of a Debian machine in the
measurements, and a container runs its host's kernel.

A package belongs to the kernel by its binary name (linux-image-..., kernel-core)
or by its source package (linux, linux-signed-*, linux-hwe-*, RPM kernel): the
packages built from the kernel source but that are not the kernel
(linux-libc-dev, linux-tools-*, perf, bpftool) carry its advisories and never
count, whatever kernel runs.
"""

import re

_DEB_PREFIXES = ("linux-image-", "linux-modules-", "linux-headers-")
_DEB_SOURCES = re.compile(r"^linux(-signed.*|-hwe.*)?$")


def _name(name):
    return (name or "").split(":")[0]


def _is_kernel_binary(name, family):
    name = _name(name)
    if family == "deb":
        return name.startswith(_DEB_PREFIXES)
    if family == "rpm":
        return name == "kernel" or name.startswith("kernel-")
    return False


def _is_kernel_source(source, family):
    if family == "deb":
        return bool(_DEB_SOURCES.match(source or ""))
    if family == "rpm":
        return source == "kernel"
    return False


def is_kernel(name, family, source=""):
    """A package of the kernel, by its binary name or its source package."""
    return _is_kernel_binary(name, family) or _is_kernel_source(source, family)


def is_running_kernel(name, version, family, running, source=""):
    """
    Whether this package is the running kernel ("uname -r"): Debian family, a
    kernel image, modules or headers package whose name ends with the running
    release; RPM, a kernel package whose version (epoch dropped) starts the
    running release. Other packages of the kernel source never are.
    """
    if not running or not _is_kernel_binary(name, family):
        return False
    if family == "deb":
        return _name(name).endswith("-" + running)
    release = (version or "").split(":", 1)[-1]
    return bool(release) and (running == release or running.startswith(release + "."))
