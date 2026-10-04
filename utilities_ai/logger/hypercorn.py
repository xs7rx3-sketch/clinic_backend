"""Hypercorn logging integration for queue-based application logging.

This module configures Hypercorn to emit access and error logs through the
application's queue-based logging pipeline, ensuring worker processes can
forward log records back to the parent process. It also validates that the
logger is configured before Hypercorn initializes its own handlers.

Note:
    The integration is only safe when the server config has not already
    initialized a logger or custom log configuration.

Example:
    >>> from hypercorn.config import Config
    >>> from utilities_ai.logger.config import LoggingConfig
    >>> server_config = Config()
    >>> logging_config = LoggingConfig(level="INFO", integrate_hypercorn=True)
    >>> configure_hypercorn(server_config, record_queue, logging_config)
"""

import logging
from logging.handlers import QueueHandler
from multiprocessing.queues import Queue
from typing import TYPE_CHECKING, Optional

from utilities_ai.exceptions import ConfigurationError

from .config import LoggingConfig
from .utils import normalize_logging_level

if TYPE_CHECKING:
    from hypercorn.config import Config as HypercornServerConfig


class _HypercornWorkerBootstrap:
    """Bootstrap Hypercorn worker processes into the shared record queue.

    Initializes the worker-specific logging state that is later restored when a
    Hypercorn worker process is spawned. The bootstrap object is attached to the
    server config and rehydrated during unpickling so each worker can configure
    itself against the same queue.

    Attributes:
        _record_queue (Queue[Optional[logging.LogRecord]]): Shared queue used to
            relay log records to the parent process.
        _logging_config (LoggingConfig): Logging configuration used to initialize
            the worker logger.
    """

    def __init__(
        self,
        record_queue: Queue[Optional[logging.LogRecord]],
        logging_config: LoggingConfig,
    ) -> None:
        """Store the shared queue and worker logging configuration.

        Args:
            record_queue: Queue that accepts log records emitted by the worker.
            logging_config: Logging configuration for this worker process.
        """

        self._record_queue = record_queue
        self._logging_config = logging_config

    def __getstate__(
        self,
    ) -> tuple[Queue[Optional[logging.LogRecord]], LoggingConfig]:
        """Return the queue and logging configuration needed to rebuild the state.

        Returns:
            A tuple containing the record queue and logging configuration.
        """

        return self._record_queue, self._logging_config

    def __setstate__(
        self,
        state: tuple[Queue[Optional[logging.LogRecord]], LoggingConfig],
    ) -> None:
        """Restore the worker bootstrap state and configure logging for the process.

        Args:
            state: A tuple containing the record queue and logging configuration.
        """

        from .setup import logging_manager

        self._record_queue, self._logging_config = state
        logging_manager.configure_worker(self._record_queue, self._logging_config)


def configure_hypercorn(
    hypercorn_server_config: "HypercornServerConfig",
    record_queue: Queue[Optional[logging.LogRecord]],
    logging_config: LoggingConfig,
) -> None:
    """Attach worker bootstrap state and connect Hypercorn loggers to the queue.

    This function stores the bootstrap object on the server config and, when
    enabled, routes Hypercorn access and error logs to the shared record queue.
    The queue-based handler keeps log records in the same delivery path as the
    rest of the application.

    Args:
        hypercorn_server_config: Hypercorn server configuration receiving the
            bootstrap and logger configuration.
        record_queue: Shared queue that receives log records from all worker
            processes.
        logging_config: Logging configuration describing the desired level and
            Hypercorn integration.

    Returns:
        None: The function mutates the provided server configuration in place.
    """

    setattr(
        hypercorn_server_config,
        "_utilities_ai_logging_bootstrap",
        _HypercornWorkerBootstrap(record_queue, logging_config),
    )

    if not logging_config.integrate_hypercorn:
        return

    hypercorn_server_config.accesslog = logging.getLogger("hypercorn.access")
    hypercorn_server_config.errorlog = logging.getLogger("hypercorn.error")

    logging_level = normalize_logging_level(logging_config.level)
    handler_name = "utilities_ai"

    hypercorn_server_config.logconfig_dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            handler_name: {
                "()": QueueHandler,
                "queue": record_queue,
            }
        },
        "loggers": {
            "hypercorn.access": {
                "handlers": [handler_name],
                "level": logging_level,
                "propagate": False,
            },
            "hypercorn.error": {
                "handlers": [handler_name],
                "level": logging_level,
                "propagate": False,
            },
        },
    }


def validate_hypercorn_configuration(
    hypercorn_server_config: "HypercornServerConfig",
    integrate_hypercorn: bool,
) -> None:
    """Reject unsafe Hypercorn logging configuration before initialization.

    Ensures the custom logger integration is configured only when Hypercorn has
    not already set up its own logging state. This prevents duplicate or
    conflicting handlers from being attached.

    Args:
        hypercorn_server_config: Hypercorn server configuration object being
            validated.
        integrate_hypercorn: Whether Hypercorn log capture should be integrated
            with the shared queue.

    Raises:
        ConfigurationError: If the server config already initializes logging or
            if Hypercorn logging was configured before integration.
    """

    if not integrate_hypercorn:
        return

    if getattr(hypercorn_server_config, "_log", None) is not None:
        raise ConfigurationError("Hypercorn logging integration must be configured before its logger is initialized")
    if hypercorn_server_config.logconfig is not None or hypercorn_server_config.logconfig_dict is not None:
        raise ConfigurationError("Hypercorn logging is already configured")
