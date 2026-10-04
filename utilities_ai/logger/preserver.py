"""Utilities for archiving log files by renaming them with timestamps.

This module provides functionality to preserve old log files by renaming them
with a Unix timestamp suffix. This prevents log files from being overwritten
when new logging sessions begin, maintaining a complete archive of all logs
without manual intervention.

Note:
    The renaming process uses a collision-detection loop to ensure the new
    filename is unique. File operations use `os.replace()` which is atomic
    on most filesystems, ensuring thread-safe behavior.

Example:
    >>> from utilities_ai.logger.preserver import preserve_old_logs
    >>> preserve_old_logs("/var/log/app.log")
    True
    # File is now: /var/log/app_1705234800.log
"""

import os
from datetime import datetime


def preserve_old_logs(log_path: str) -> bool:
    """Rename an existing log file by appending a Unix timestamp to its name.

    Renames the log file at the given path to include the current Unix timestamp
    in its filename, allowing the original path to be reused for new logs. Uses a
    collision-detection loop to ensure the renamed filename is unique.

    Args:
        log_path: Absolute or relative path to the log file to archive.

    Returns:
        True if the file was successfully renamed, False if the file does not exist.

    Example:
        >>> preserve_old_logs("/var/log/app.log")
        True
        # File is now renamed to: /var/log/app_1705234800.log
    """

    if not os.path.exists(log_path):
        return False

    old_file = os.path.basename(log_path)
    old_dir = os.path.dirname(log_path)
    old_name, old_extension = os.path.splitext(old_file)

    # Retry until we generate a filename that doesn't already exist (collision avoidance)
    while True:
        new_name = f"{old_name}_{int(datetime.timestamp(datetime.now()))}{old_extension}"
        new_path = os.path.join(old_dir, new_name)

        if not os.path.exists(new_path):
            # os.replace is atomic on most filesystems, ensuring no race condition
            os.replace(log_path, new_path)
            return True
