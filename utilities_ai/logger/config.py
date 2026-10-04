"""Configuration models for the logger subsystem.

This module defines validation-aware dataclasses used to configure log
output, redaction behavior, and runtime integration with the application.
It centralizes the guardrails for file rotation, console output, and log
level selection so that invalid settings fail early with a consistent
ConfigurationError.

Note:
    Instances are frozen dataclasses. Validation happens in __post_init__
    so configuration errors are raised immediately when a config object is
    created.

Example:
    >>> config = LoggingConfig(enabled=True, level="INFO")
    >>> config.level
    'INFO'
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from utilities_ai.exceptions import ConfigurationError

from .defaults import (
    DEFAULT_CONSOLE_FORMAT,
    DEFAULT_ENABLE_LOGGER,
    DEFAULT_FILE_FORMAT,
    DEFAULT_LOG_FILE_PATH,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_FILE_SIZE,
    DEFAULT_RETAINED_FILE_COUNT,
    DEFAULT_SENSITIVE_KEYS,
)

# TODO: Currently, these config dataclasses are exposed to end-users so that they can configure the logger.
# I'm not sure this is the most appropriate method, so we should think more about this.


@dataclass(frozen=True)
class FileConfig:
    """Configure a rotating file sink for application logs.

    The values in this dataclass are validated as soon as the object is
    instantiated so invalid file settings raise a ConfigurationError before
    logging begins.

    Attributes:
        file_path (str | Path): Destination path for the log file.
        max_file_size (int): Maximum size of each log file in bytes.
        retained_file_count (int): Number of rotated files to keep.
        compress_rotated_files (bool): If True, compressed backups are used
            after rotation.
        format (str): Log record format string for file output.

    Example:
        >>> config = FileConfig(file_path="/tmp/app.log", max_file_size=1024)
        >>> config.path.name
        'app.log'
    """

    file_path: str | Path = DEFAULT_LOG_FILE_PATH
    max_file_size: int = DEFAULT_MAX_FILE_SIZE  # In bytes
    retained_file_count: int = DEFAULT_RETAINED_FILE_COUNT
    compress_rotated_files: bool = False
    format: str = DEFAULT_FILE_FORMAT

    def __post_init__(self) -> None:
        """Validate file logging configuration values.

        Raises:
            ConfigurationError: If the file path, rotation settings, or format
                are invalid.
        """

        if isinstance(self.file_path, str) and not self.file_path.strip():
            raise ConfigurationError("Log file path cannot be empty")
        if self.max_file_size <= 0:
            raise ConfigurationError("Maximum log file size must be greater than zero")
        if self.retained_file_count <= 0:
            raise ConfigurationError("Retained log file count must be greater than zero")
        if not self.format.strip():
            raise ConfigurationError("File log format cannot be empty")

    @property
    def path(self) -> Path:
        """Return the configured file path as a pathlib.Path object.

        Returns:
            Path: Absolute or relative file path represented by the config.
        """

        return Path(self.file_path)


@dataclass(frozen=True)
class RedactionConfig:
    """Configure how sensitive content is masked in logs.

    Matching can be driven by specific field names, regular-expression
    patterns, or both. This class prevents a misconfigured redaction setup
    from silently disabling protection.

    Attributes:
        sensitive_keys (Iterable[str]): Structured field names that should be
            redacted when they appear in log records.
        patterns (Iterable[str]): Regex patterns matched against log messages.
        include_default_patterns (bool): If True, the default redaction patterns
            are enabled in addition to any custom rules.
        replacement (str): Placeholder inserted in place of sensitive values.
    """

    sensitive_keys: Iterable[str] = DEFAULT_SENSITIVE_KEYS
    patterns: Iterable[str] = field(default_factory=set)
    include_default_patterns: bool = True
    replacement: str = "[REDACTED]"

    def __post_init__(self) -> None:
        """Validate the redaction configuration.

        Raises:
            ConfigurationError: If redaction is enabled without any keys or
                patterns to match.
        """

        if not self.include_default_patterns and not (self.sensitive_keys or self.patterns):
            raise ConfigurationError("Cannot redact logs without sensitive keys or patterns")


@dataclass(frozen=True)
class LoggingConfig:
    """Describe the runtime behavior of the application logger.

    This configuration defines whether logging is active, which log level is
    used, how console output is formatted, and whether file output or
    redaction rules are applied. Validation ensures the settings are
    internally consistent before they are consumed by the logger setup.

    Attributes:
        enabled (bool): If True, logging is activated for the application.
        level (str): Logging severity threshold, such as INFO or ERROR.
        console_format (Optional[str]): Formatter string for console output.
        file (Optional[FileConfig]): Optional file sink configuration.
        redaction (Optional[RedactionConfig]): Optional redaction rules.
        integrate_hypercorn (bool): If True, the logger is configured for
            Hypercorn lifecycle events.
    """

    enabled: bool = DEFAULT_ENABLE_LOGGER
    level: str = DEFAULT_LOG_LEVEL
    console_format: Optional[str] = DEFAULT_CONSOLE_FORMAT
    file: Optional[FileConfig] = None
    redaction: Optional[RedactionConfig] = None
    integrate_hypercorn: bool = False

    def __post_init__(self) -> None:
        """Validate a complete logging configuration.

        Raises:
            ConfigurationError: If the logger is enabled with invalid values or
                no valid output destination.
        """

        if not self.enabled:
            return

        self._validate_log_level()

        if self.console_format is not None and not self.console_format.strip():
            raise ConfigurationError("Console log format cannot be empty")
        if self.console_format is None and self.file is None:
            raise ConfigurationError("At least one log destination must be configured")

    def _validate_log_level(self) -> None:
        """Verify that the configured log level is recognized by Python logging.

        Raises:
            ConfigurationError: If the level is empty or not a valid logging
                level name.
        """

        if not self.level.strip():
            raise ConfigurationError("Log level cannot be empty")

        normalized_level = self.level.strip().upper()
        try:
            logging.getLevelNamesMapping()[normalized_level]
        except KeyError as error:
            raise ConfigurationError(f"Unknown logging level: {self.level}") from error


__all__ = ["FileConfig", "LoggingConfig", "RedactionConfig"]
