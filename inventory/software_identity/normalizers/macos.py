from .cpe import CpeNormalizer


class MacosNormalizer(CpeNormalizer):
    """
    macOS applications. On macOS the publisher field holds the origin given by
    system_profiler: "Apple" means an application shipped with the OS, covered
    by the macOS version itself.
    """

    family = "macos"

    def is_os_component(self, record):
        return record.publisher.strip().lower() == "apple"
