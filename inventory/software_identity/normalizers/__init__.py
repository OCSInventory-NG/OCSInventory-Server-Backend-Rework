from .linux import LinuxNormalizer
from .macos import MacosNormalizer
from .windows import WindowsNormalizer


def build_normalizers(matcher, decisions, origins=None):
    """One normalizer per platform family. origins: {name lowercased: distribution}."""
    return {
        "deb": LinuxNormalizer("deb", origins),
        "rpm": LinuxNormalizer("rpm", origins),
        "windows": WindowsNormalizer(matcher, decisions),
        "macos": MacosNormalizer(matcher, decisions),
    }
