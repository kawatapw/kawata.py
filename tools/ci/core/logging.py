"""Logging helpers for the CI tool.

The goal of this module is to provide a consistent logging configuration
across all modules while keeping the public API minimal: a single
`setup_logging` function and a convenience `get_logger` wrapper around
`logging.getLogger`.
"""
import logging
import sys
from typing import Dict, Any


def setup_logging(config: Dict[str, Any]) -> None:
    """Configure the root logger based on tool configuration.

    The current implementation respects a single ``debug`` flag which,
    when truthy, switches logging to DEBUG level; otherwise INFO is used.
    All log records are emitted to stderr with a verbose, timestamped
    format suitable for CI logs.

    Args:
        config: Configuration dictionary for the current run. Only the
            ``debug`` key is consulted, but additional logging-related
            options may be added in the future.
    """
    level = logging.DEBUG if config.get('debug') else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for use in modules.

    This is a thin wrapper around `logging.getLogger` provided mainly for
    symmetry with `setup_logging`.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        A `logging.Logger` instance with the global configuration applied.
    """
    return logging.getLogger(name)
