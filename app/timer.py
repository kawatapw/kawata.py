"""
Timer Module - Context Manager for Performance Timing

This module provides a simple context manager for measuring execution time
of code blocks in the osu! server application. It implements the context
manager protocol to allow easy timing of operations using Python's `with`
statement.

The Timer class is designed for performance monitoring and debugging,
allowing developers to measure how long specific operations take to execute.
It's particularly useful for database queries, API calls, and other operations
where timing information is valuable for optimization.

Key Features:
    - Context manager protocol implementation
    - Automatic start/stop timing with `with` statement
    - Manual start/stop control available
    - Elapsed time calculation in seconds
    - Type-safe implementation with proper type hints
    - Simple and lightweight design

Integration Points:
    - Database query timing in app/adapters/database.py
    - API request timing in app/api/middlewares.py
    - Performance monitoring throughout the application
    - Debug logging in app/logging.py

Usage Pattern:
    # Using as context manager
    with Timer() as timer:
        # Perform some operation
        result = await some_async_operation()

    elapsed_time = timer.elapsed()
    print(f"Operation took {elapsed_time:.2f} seconds")

    # Manual timing
    timer = Timer()
    timer.start_time = time.time()
    # ... do work ...
    timer.end_time = time.time()
    elapsed = timer.elapsed()

Related Files:
    - app/api/middlewares.py: HTTP request timing
    - app/adapters/database.py: Database query timing
    - app/logging.py: Performance logging utilities
"""

from __future__ import annotations

import time
from types import TracebackType


class Timer:
    """Context manager for measuring execution time of code blocks.

    This class provides a simple way to measure how long operations take
    to execute. It can be used as a context manager with the `with` statement
    or manually controlled with start/stop methods.

    Attributes:
        start_time: Timestamp when timing started (seconds since epoch)
        end_time: Timestamp when timing ended (seconds since epoch)
    """

    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> Timer:
        """Start timing when entering the context manager."""
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop timing when exiting the context manager."""
        self.end_time = time.time()

    def elapsed(self) -> float:
        """Calculate and return the elapsed time in seconds.

        Returns:
            Elapsed time in seconds as a float

        Raises:
            ValueError: If timer has not been started or stopped
        """
        if self.start_time is None or self.end_time is None:
            raise ValueError("Timer has not been started or stopped.")
        return self.end_time - self.start_time
