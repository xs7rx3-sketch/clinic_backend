"""Time utility functions for working with Unix timestamps.

Provides utility functions for obtaining the current time in Unix timestamp
format (milliseconds). Useful for logging, metrics, synchronization, and any
scenario requiring precision timestamps across distributed systems.

Example:
    >>> from utilities_ai.chains.helpers.time_operations import current_time_unix
    >>> now_ms = current_time_unix()
    >>> print(now_ms)
    1716043200000
"""

from datetime import datetime


def current_time_unix() -> int:
    """Return the current Unix timestamp in milliseconds.

    Obtains the current time from the system clock and converts it to a Unix
    timestamp in milliseconds. The returned value is the number of milliseconds
    since the Unix epoch (1970-01-01 00:00:00 UTC).

    Returns:
        Current time as a Unix timestamp in milliseconds.

    Example:
        >>> timestamp_ms = current_time_unix()
        >>> isinstance(timestamp_ms, int)
        True
        >>> timestamp_ms > 0
        True
    """
    return int(datetime.now().timestamp() * 1000)
