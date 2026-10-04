"""Utilities for normalizing Python logging levels.

This module provides helpers for converting user-provided level names into
standard-library logging constants. It is designed for environments where
logging configuration values may be supplied as strings and need to be
validated before use.

Note:
    Level names are matched case-insensitively after trimming surrounding
    whitespace. Unsupported values raise a ValueError instead of propagating
    a low-level lookup error.

Example:
    >>> normalize_logging_level("INFO")
    20
"""

import logging


def normalize_logging_level(level: str) -> int:
    """Normalize a logging level name to its standard library integer value.

    Converts a level name such as "INFO" or "debug" into the corresponding
    numeric logging level constant used by Python's logging module.

    Args:
        level: The logging level name to normalize. Leading and trailing
            whitespace are ignored and the value is compared
            case-insensitively.

    Returns:
        The integer logging level constant associated with the provided name.

    Raises:
        ValueError: If the supplied level name is not a valid logging level.

    Example:
        >>> normalize_logging_level("warning")
        30
    """

    normalized_level = level.strip().upper()
    try:
        return logging.getLevelNamesMapping()[normalized_level]
    except KeyError as exc:
        raise ValueError(f"Unsupported logging level: {level!r}.") from exc
