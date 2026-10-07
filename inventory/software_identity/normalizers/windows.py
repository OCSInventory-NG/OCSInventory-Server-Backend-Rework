from .cpe import CpeNormalizer


class WindowsNormalizer(CpeNormalizer):
    """Windows applications."""

    family = "windows"
