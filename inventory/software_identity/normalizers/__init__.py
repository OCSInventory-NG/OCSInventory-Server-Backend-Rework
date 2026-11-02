from .linux import LinuxNormalizer
from .macos import MacosNormalizer
from .windows import WindowsNormalizer


def build_normalizers(matcher, decisions, origins=None, thresholds=None):
    """
    One normalizer per platform family. origins: {name lowercased:
    distribution}; thresholds: (CPE match score, review score).
    """
    return {
        "deb": LinuxNormalizer("deb", origins),
        "rpm": LinuxNormalizer("rpm", origins),
        "windows": WindowsNormalizer(matcher, decisions, thresholds),
        "macos": MacosNormalizer(matcher, decisions, thresholds),
    }
