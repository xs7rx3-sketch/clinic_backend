"""Redact sensitive values from log records before they are emitted.

This module centralizes log sanitization so structured fields and message
text can be scrubbed consistently before records reach their handlers. It
applies configured sensitive-key replacements and optional regex-based
pattern matching to the final message string.

Note:
    This component mutates the provided LogRecord in place and does not
    return a copy of the record.

Example:
    >>> from utilities_ai.logger.config import RedactionConfig
    >>> config = RedactionConfig(sensitive_keys=["password"], replacement="[REDACTED]")
    >>> redactor = Redactor(config)
"""

import logging
import re

from utilities_ai.exceptions import ConfigurationError

from .config import RedactionConfig
from .defaults import DEFAULT_REDACTION_PATTERNS


class Redactor:
    """Redact sensitive values from queued log records.

    Applies key-based scrubbing for configured structured fields and
    regex-based replacement for message text. Instances are lightweight and
    may be reused across multiple log records.

    Example:
        >>> import logging
        >>> from utilities_ai.logger.config import RedactionConfig
        >>> config = RedactionConfig(sensitive_keys=["token"], replacement="[REDACTED]")
        >>> redactor = Redactor(config)
        >>> record = logging.LogRecord("name", logging.INFO, __file__, 1, "token=abc", (), None)
        >>> redactor.redact(record)
        >>> record.getMessage()
        'token=[REDACTED]'
    """

    def __init__(self, redaction_config: RedactionConfig) -> None:
        """Initialize the redactor using the configured sensitive keys and patterns.

        Args:
            redaction_config: Redaction settings that define which keys are
                treated as sensitive, the replacement value, and any
                additional regex patterns to apply.

        Note:
            The configuration is normalized to case-insensitive keys and
            compiled once at initialization so later calls avoid repeated
            regex setup.
        """

        self._sensitive_keys = frozenset(key.casefold() for key in redaction_config.sensitive_keys)
        self._replacement = redaction_config.replacement
        self._patterns = self._compile_patterns(redaction_config)

    def redact(self, record: logging.LogRecord) -> None:
        """Redact sensitive field names and message text in place.

        Iterates through the record's attributes, replaces any field whose name
        matches a configured sensitive key, and scrubs message text using all
        compiled regex patterns.

        Args:
            record: Log record whose fields and message should be sanitized.

        Returns:
            None: The record is mutated in place and no new object is returned.

        Note:
            The method replaces the record's message and clears the args tuple so
            the formatted message remains deterministic after sanitization.
        """

        for field_name in record.__dict__:
            if field_name.casefold() in self._sensitive_keys:
                record.__dict__[field_name] = self._replacement

        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(lambda _match: self._replacement, message)

        record.msg = message
        record.args = None

    @staticmethod
    def _compile_patterns(redaction_config: RedactionConfig) -> frozenset[re.Pattern[str]]:
        """Compile the configured redaction patterns into reusable regex objects.

        Args:
            redaction_config: Redaction settings including any default patterns
                to merge with custom user-provided patterns.

        Returns:
            A frozenset of compiled regular-expression patterns.

        Raises:
            ConfigurationError: If any configured pattern is invalid and cannot
                be compiled.
        """

        patterns: list[str] = []
        if redaction_config.include_default_patterns:
            patterns.extend(DEFAULT_REDACTION_PATTERNS)
        patterns.extend(redaction_config.patterns)

        compiled_patterns: list[re.Pattern[str]] = []
        for pattern in patterns:
            try:
                compiled_patterns.append(re.compile(pattern))
            except re.error as error:
                raise ConfigurationError(f"Invalid redaction pattern: {error}") from error

        return frozenset(compiled_patterns)
