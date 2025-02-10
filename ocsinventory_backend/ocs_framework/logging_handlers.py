import logging

from django.apps import apps


class DynamicLogLevelHandler(logging.Handler):
    """
    Handler that updates the log level based on server configuration
    """

    def __init__(self, base_handler, **kwargs):
        # Use the provided level or default to NOTSET.
        level = kwargs.pop("level", logging.NOTSET)
        super().__init__(level)
        self.base_handler = base_handler
        self._update_level()

    def emit(self, record):
        """
        Rely on the base handler to emit the record
        """
        self.base_handler.emit(record)

    def _update_level(self):
        """
        Update the log level using the server configuration.
        """
        if not apps.ready:
            return
        try:
            from config.models import Config

            server_config = Config.objects.get(name="server")

            # find log level setting
            log_level_setting = next(
                (
                    setting
                    for setting in server_config.value
                    if setting["name"] == "log_level"
                ),
                None,
            )
            if log_level_setting and log_level_setting["value"]:
                level_str = log_level_setting["value"].upper()
                new_level = getattr(logging, level_str, logging.INFO)
            else:
                new_level = logging.INFO

            self.setLevel(new_level)
            self.base_handler.setLevel(new_level)

        except Exception as e:
            logging.error(f"Error updating log level: {e}")
            self.setLevel(logging.INFO)
            self.base_handler.setLevel(logging.INFO)
            logging.debug(
                "DynamicLogLevelHandler: Log level set to default INFO due to error"
            )
