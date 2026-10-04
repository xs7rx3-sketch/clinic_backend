"""Configure and manage the shared application logger.

This module centralizes logger setup for the application, worker processes,
and Hypercorn integrations. It creates a single queue-backed listener that
serializes emitted log records to console and file handlers and can redact
sensitive values before data reaches the output sinks.

Note:
    This module is intended to be configured once per process. Reconfiguring
    the logger without calling shutdown() raises ConfigurationError.

Example:
    >>> from utilities_ai.logger.setup import logging_manager
    >>> logger = logging_manager.logger
"""

import logging
import sys
import warnings
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import get_context
from multiprocessing.queues import Queue
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Optional

from concurrent_log_handler import ConcurrentRotatingFileHandler

from utilities_ai.exceptions import ConfigurationError

from .config import FileConfig, LoggingConfig
from .defaults import DEFAULT_ENABLE_LOGGER, DEFAULT_LOG_LEVEL
from .hypercorn import configure_hypercorn, validate_hypercorn_configuration
from .redactor import Redactor
from .utils import normalize_logging_level

if TYPE_CHECKING:
    from hypercorn.config import Config as HypercornServerConfig


class _RedactionHandler(logging.Handler):
    """Redact records before the queue listener emits them to downstream handlers.

    The handler runs first in the listener chain so each record is sanitized
    before console or file handlers write it out.

    Args:
        redactor: Redaction rules used to sanitize log records in place.
    """

    def __init__(self, redactor: Redactor) -> None:
        """Initialize the redaction handler with its configured redactor.

        Args:
            redactor: Rules used to scrub sensitive values from a LogRecord.
        """

        super().__init__()
        self._redactor = redactor

    def emit(self, record: logging.LogRecord) -> None:
        """Sanitize a record before it is forwarded to the queue listener.

        Args:
            record: Log message to redact in place.
        """

        self._redactor.redact(record)


class LoggingManager:
    """Manage the shared queue-backed logger and listener thread for the app.

    The manager owns the application logger instance and the queue listener that
    writes events to the configured console and file handlers. Configure the
    manager before starting worker processes and call shutdown() when tearing
    the process down.
    """

    def __init__(self) -> None:
        """Initialize the manager state and application logger."""

        self._logger = logging.getLogger("utilities_ai.application")
        self._lock = RLock()
        self._record_queue: Optional[Queue[Optional[logging.LogRecord]]] = None
        self._queue_listener: Optional[QueueListener] = None

    @property
    def logger(self) -> logging.Logger:
        """Return the application logger owned by this manager.

        Returns:
            The process-wide logger configured for the application.
        """

        return self._logger

    def configure(
        self,
        logging_config: LoggingConfig,
        *,
        hypercorn_server_config: Optional["HypercornServerConfig"] = None,
    ) -> None:
        """Start centralized output handling and attach the application logger.

        Args:
            logging_config: Full logging configuration for the process.
            hypercorn_server_config: Optional Hypercorn configuration object used when
                Hypercorn logging integration is enabled.

        Raises:
            ConfigurationError: If logging is already configured in this process, or if
                Hypercorn integration is requested without a server config.
        """

        with self._lock:
            if not logging_config.enabled:
                self._remove_handlers(self._logger)
                self._logger.disabled = True
                return

            if self._queue_listener is not None:
                raise ConfigurationError("Logging is already configured in this process")

            logging_level = normalize_logging_level(logging_config.level)
            if logging_config.integrate_hypercorn and hypercorn_server_config is None:
                raise ConfigurationError("hypercorn_server_config is required when Hypercorn logging is enabled")
            if hypercorn_server_config is not None:
                validate_hypercorn_configuration(
                    hypercorn_server_config,
                    logging_config.integrate_hypercorn,
                )

            redactor = Redactor(logging_config.redaction) if logging_config.redaction is not None else None
            handlers = self._create_output_handlers(logging_config, logging_level)
            if redactor is not None:
                handlers.insert(0, _RedactionHandler(redactor))
            record_queue = get_context("spawn").Queue()
            queue_listener = QueueListener(
                record_queue,
                *handlers,
                respect_handler_level=True,
            )
            listener_started = False

            try:
                queue_listener.start()
                listener_started = True
                self._connect_logger_to_queue(self._logger, record_queue, logging_level)
                if hypercorn_server_config is not None:
                    configure_hypercorn(
                        hypercorn_server_config,
                        record_queue,
                        logging_config,
                    )
            except Exception:
                self._remove_handlers(self._logger)
                self._logger.disabled = True
                if listener_started:
                    queue_listener.stop()
                self._close_output_handlers(queue_listener.handlers)
                record_queue.close()
                record_queue.join_thread()
                raise

            self._record_queue = record_queue
            self._queue_listener = queue_listener

    def configure_worker(
        self,
        record_queue: Queue[Optional[logging.LogRecord]],
        logging_config: LoggingConfig,
    ) -> None:
        """Connect a worker logger to an existing parent logger queue.

        The worker does not create its own output handlers or listener; it only
        forwards records to the parent queue so the parent process handles the
        actual formatting and persistence.

        Args:
            record_queue: Queue created by the parent process for shared logging.
            logging_config: Runtime configuration for the worker logger.
        """

        if not logging_config.enabled:
            self._remove_handlers(self._logger)
            self._logger.disabled = True
            return

        logging_level = normalize_logging_level(logging_config.level)
        self._connect_logger_to_queue(self._logger, record_queue, logging_level)

    def shutdown(self) -> None:
        """Stop the queue listener and close all managed logging resources.

        This method detaches the application logger, stops the listener thread,
        flushes all handlers, and closes the shared queue.
        """

        with self._lock:
            queue_listener = self._queue_listener
            record_queue = self._record_queue
            if queue_listener is None or record_queue is None:
                return

            self._remove_handlers(self._logger)
            self._logger.disabled = True
            self._queue_listener = None
            self._record_queue = None

            queue_listener.stop()
            self._close_output_handlers(queue_listener.handlers)
            record_queue.close()
            record_queue.join_thread()

    @staticmethod
    def _remove_handlers(logger: logging.Logger) -> None:
        """Remove and close every handler attached to a logger.

        Args:
            logger: Logger whose handlers should be detached.
        """

        for handler in tuple(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

    def _connect_logger_to_queue(
        self,
        logger: logging.Logger,
        record_queue: Queue[Optional[logging.LogRecord]],
        logging_level: int,
    ) -> None:
        """Attach a logger to a shared queue so records are emitted on the listener thread.

        Args:
            logger: Logger to reconfigure for queue-based delivery.
            record_queue: Shared multiprocessing queue that receives LogRecord objects.
            logging_level: Numeric logging level to assign to the logger.
        """

        self._remove_handlers(logger)
        logger.setLevel(logging_level)
        logger.propagate = False
        logger.disabled = False
        logger.addHandler(QueueHandler(record_queue))

    @staticmethod
    def _create_output_handlers(
        logging_config: LoggingConfig,
        logging_level: int,
    ) -> list[logging.Handler]:
        """Build the console and file handlers used by the queue listener.

        Args:
            logging_config: Logging configuration that includes console and file settings.
            logging_level: Effective minimum level for registered handlers.

        Returns:
            A list of configured logging handlers to be attached to the queue listener.
        """

        handlers: list[logging.Handler] = []

        if logging_config.console_format is not None:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging_level)
            console_handler.setFormatter(logging.Formatter(logging_config.console_format))
            handlers.append(console_handler)

        file_config = logging_config.file
        if file_config is not None:
            file_config.path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = ConcurrentRotatingFileHandler(
                file_config.path,
                maxBytes=file_config.max_file_size,
                backupCount=file_config.retained_file_count,
                encoding="utf-8",
                use_gzip=file_config.compress_rotated_files,
            )
            file_handler.setLevel(logging_level)
            file_handler.setFormatter(logging.Formatter(file_config.format))
            handlers.append(file_handler)

        return handlers

    @staticmethod
    def _close_output_handlers(handlers: tuple[logging.Handler, ...]) -> None:
        """Flush and close all output handlers attached to the listener.

        Args:
            handlers: Handlers owned by the queue listener.
        """

        for handler in handlers:
            handler.flush()
            handler.close()


logging_manager = LoggingManager()


def setup_logger(
    enable: bool = DEFAULT_ENABLE_LOGGER,
    detailed: bool = False,
    log_path: Optional[str] = None,
    *,
    rotation: Optional[str] = None,
    retention: Optional[str] = None,
) -> logging.Logger:
    """Configure logging through the legacy entry point.

    This compatibility wrapper delegates to the shared manager while preserving
    the historical API. It is deprecated and emits a DeprecationWarning.

    Args:
        enable: If True, enable logging for the application logger.
        detailed: If True, use DEBUG level instead of the default level.
        log_path: Optional path to a log file; if provided, a file handler is configured.
        rotation: Unsupported in the legacy API and rejected if provided.
        retention: Unsupported in the legacy API and rejected if provided.

    Returns:
        The configured application logger instance.

    Raises:
        ConfigurationError: If legacy rotation or retention arguments are passed.
    """

    warnings.warn(
        "setup_logger() is deprecated; configure logging_manager directly",
        DeprecationWarning,
        stacklevel=2,
    )
    if rotation is not None or retention is not None:
        raise ConfigurationError("Legacy rotation and retention policies are not supported; use FileConfig size and backup-count settings")

    file_config = None
    if log_path is not None:
        path = Path(log_path)
        file_config = FileConfig(path)

    logging_manager.configure(LoggingConfig(enabled=enable, level="DEBUG" if detailed else DEFAULT_LOG_LEVEL, file=file_config))
    return logging_manager.logger
