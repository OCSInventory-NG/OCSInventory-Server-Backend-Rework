"""
Progress of long steps (downloads, bulk writes), logged at DEBUG at most
every few seconds so that a task that seems stuck can be followed.
"""

import logging
import time

INTERVAL = 5
MB = 1 << 20


def _size(amount):
    return f"{amount / MB:.1f} MB"


class Progress:
    """
    Counts what a step went through and logs it, at most every `interval`
    seconds: "label: 12.0 / 84.0 MB (14%)", or "label: 5000 / 41234 (12%)".
    """

    def __init__(
        self, logger, label, total=None, in_bytes=False, interval=None, clock=None
    ):
        self.logger = logger
        self.label = label
        self.total = total or None
        self.in_bytes = in_bytes
        self.interval = INTERVAL if interval is None else interval
        self.clock = clock or time.monotonic
        self.done = 0
        self.finished = False
        self.started = self.last = self.clock()

    def _format(self, amount):
        return _size(amount) if self.in_bytes else str(amount)

    def message(self):
        text = f"{self.label}: {self._format(self.done)}"
        if self.total:
            text += f" / {self._format(self.total)}"
            text += f" ({min(100, self.done * 100 // self.total)}%)"
        return text

    def advance(self, amount=1):
        self.done += amount
        now = self.clock()
        if now - self.last >= self.interval and self.logger.isEnabledFor(logging.DEBUG):
            self.last = now
            self.logger.debug(self.message())

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.logger.debug(
            "%s in %.0f s", self.message(), max(0, self.clock() - self.started)
        )

    def count(self, iterable):
        """Yields the items of an iterable, each one counted."""
        for item in iterable:
            self.advance()
            yield item
        self.finish()


class ProgressStream:
    """A readable stream whose bytes read are counted by a Progress."""

    def __init__(self, stream, progress):
        self.stream = stream
        self.progress = progress

    def read(self, size=-1):
        data = self.stream.read(size)
        if data:
            self.progress.advance(len(data))
        else:
            self.progress.finish()
        return data


def content_length(response):
    try:
        return int((response.headers or {}).get("Content-Length") or 0) or None
    except (TypeError, ValueError):
        return None
