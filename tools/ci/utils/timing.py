"""Timing and duration utilities for the CI tool.

These helpers are used to capture wall-clock timings for CI stages and
render them in a consistent, human-readable form in logs and reports.
"""

from __future__ import annotations

import time
from datetime import UTC
from datetime import datetime
from typing import Any


class Timer:
    """Context manager-style timer for measuring execution time.

    The timer records start and end timestamps (in seconds since the epoch)
    and can produce both a raw duration and a structured dictionary
    representation suitable for serialization.
    """

    def __init__(self, name: str = "timer"):
        """Initialize a new timer instance.

        Args:
            name: Logical name for the timed operation, used in
                `get_result` for identification.
        """
        self.name = name
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> Timer:
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        """Return the measured duration in seconds.

        If the timer has not been started, this returns ``0.0``; if the
        timer is currently running, it measures up to the current time.
        """
        if self.start_time is None:
            return 0.0
        # Coderabbit: explicit None check so a valid 0.0 epoch end_time
        # isn't mistaken for "still running" (truthiness would call
        # time.time() instead).
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time

    def get_result(self) -> dict[str, Any]:
        """Return a structured representation of the timing result.

        Returns:
            A mapping containing the timer name, ISO 8601 start and end
            timestamps (when available), and the duration in seconds.
        """
        return {
            "name": self.name,
            "start": (
                datetime.fromtimestamp(self.start_time, tz=UTC).isoformat()
                if self.start_time is not None
                else None
            ),
            "end": (
                datetime.fromtimestamp(self.end_time, tz=UTC).isoformat()
                if self.end_time is not None
                else None
            ),
            "duration": self.duration,
        }


def format_duration(seconds: float) -> str:
    """Format a duration in seconds into a compact human-readable string.

    Examples:

    - ``12.3`` → ``\"12.3s\"``
    - ``90`` → ``\"1m30s\"``
    - ``7200`` → ``\"2h0m\"``

    Args:
        seconds: Duration in seconds.

    Returns:
        A short string representation suitable for logs and summaries.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs}s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h{minutes}m"


def get_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()
