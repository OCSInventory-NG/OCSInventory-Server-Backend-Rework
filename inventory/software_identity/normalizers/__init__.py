from .linux import LinuxNormalizer
from .macos import MacosNormalizer
from .windows import WindowsNormalizer


def build_normalizers(matcher, decisions):
    """One normalizer per platform family."""
    return {
        "deb": LinuxNormalizer("deb"),
        "rpm": LinuxNormalizer("rpm"),
        "windows": WindowsNormalizer(matcher, decisions),
        "macos": MacosNormalizer(matcher, decisions),
    }
