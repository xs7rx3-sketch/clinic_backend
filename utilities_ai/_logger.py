import atexit
import logging
import os
import sys
from logging.handlers import QueueHandler, QueueListener
from queue import SimpleQueue
from typing import Optional

from .defaults import DEFAULT_ENABLE_LOGGER, DEFAULT_LOG_LEVEL


def _configure_internal_logger() -> tuple[logging.Logger, Optional[QueueListener]]:
    """Configure package-internal console logging with a local queue/listener thread.

    Separate from reusable application logging, it keeps output off calling threads
    and lets the module drain queued records at shutdown.
    """

    internal_logger = logging.getLogger("utilities_ai")
    internal_logger.handlers.clear()
    internal_logger.propagate = False

    enabled_value = os.getenv("UTILITIES_AI_ENABLE_LOGGER", str(DEFAULT_ENABLE_LOGGER)).strip().casefold()
    if enabled_value != "true":
        internal_logger.disabled = True
        return internal_logger, None

    logging_level = os.getenv("UTILITIES_AI_LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper() or DEFAULT_LOG_LEVEL
    internal_logger.setLevel(logging_level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging_level)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | " "%(name)s:%(funcName)s:%(lineno)d - %(message)s"))

    record_queue = SimpleQueue()
    queue_listener = QueueListener(record_queue, stream_handler, respect_handler_level=True)

    internal_logger.addHandler(QueueHandler(record_queue))
    internal_logger.disabled = False
    queue_listener.start()

    return internal_logger, queue_listener


log, _queue_listener = _configure_internal_logger()
if _queue_listener is not None:
    atexit.register(_queue_listener.stop)

__all__ = ["log"]
