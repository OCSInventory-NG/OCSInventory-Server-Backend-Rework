import logging


class DynamicLogLevelManager:
    """
    Manages and applies per-logger dynamic log levels.
    """

    LOGGER_MAPPING = {
        "log_level_backend": ["", "auth"],
        "log_level_django": ["django"],
        "log_level_collection": ["asset.collection.views"],
        "log_level_management": ["mgmt.management.commands"],
    }

    def __init__(self):
        self.levels = {}
        self.logger = logging.getLogger(__name__)
        self.update_from_config()

    def update_from_config(self):
        """
        Pulls all log levels from the Config model and applies them individually.
        """
        try:
            from config.models import Config

            server_config = Config.objects.get(name="server")
            values = {item["name"]: item["value"] for item in server_config.value}

            for config_key, logger_names in self.LOGGER_MAPPING.items():
                level_str = values.get(config_key, "DEBUG")
                is_default = config_key not in values
                for logger_name in logger_names:
                    self.set_level_for_logger(logger_name, level_str, is_default)

        except Exception as e:
            self.logger.error(f"Failed to fetch config: {e}")
            # all loggers to default value if anything goes wrong
            for logger_names in self.LOGGER_MAPPING.values():
                for logger_name in logger_names:
                    self.set_level_for_logger(logger_name, "DEBUG", True)

    def set_level_for_logger(
        self, logger_name: str, level_str: str, is_default: bool = False
    ):
        """
        Applies a level string like "INFO", "DEBUG", etc. to a specific logger.
        """
        level = getattr(logging, level_str.upper(), logging.DEBUG)
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
        self.levels[logger_name] = level
        default_msg = " (using default)" if is_default else ""
        self.logger.warning(
            f"{logger_name or 'root'} level set"
            f" to {logging.getLevelName(level)}{default_msg}"
        )


def add_console_handler(logger_names, stream):
    """
    Mirror the given loggers to a stream, on top of their usual handlers.

    Returns:
        logging.StreamHandler: handler added to each logger
    """
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        logging.Formatter(fmt="[{levelname}][{asctime}][{name}]: {message}", style="{")
    )
    for logger_name in logger_names:
        logging.getLogger(logger_name).addHandler(handler)
    return handler
