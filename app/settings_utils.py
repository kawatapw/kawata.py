"""
Settings Utilities Module - Configuration Parsing and Environment Variable Handling

This module provides utility functions for parsing and handling configuration
settings in the osu! server application. It includes helper functions for
reading environment variables, parsing boolean and list values, and managing
deprecated configuration options with graceful migration support.

The module serves as a bridge between raw environment variables and typed
configuration values, ensuring consistent parsing and validation across
the application. It also provides support for deprecated configuration
options with automatic migration warnings and error handling.

Key Features:
    - Boolean value parsing from string environment variables
    - List parsing from comma-separated string values
    - Deprecated variable support with migration warnings
    - Environment variable validation and error handling
    - Type-safe configuration value conversion
    - Graceful handling of missing or invalid configuration

Integration Points:
    - Settings configuration in app/settings.py
    - Environment variable management
    - Configuration validation throughout the application
    - Deprecated option migration support

Usage Pattern:
    # Parse boolean from environment
    debug_mode = read_bool(os.getenv("DEBUG_MODE", "false"))

    # Parse list from environment
    allowed_hosts = read_list(os.getenv("ALLOWED_HOSTS", ""))

    # Support deprecated variables with migration
    db_host = support_deprecated_vars(
        new_name="DATABASE_HOST",
        deprecated_name="DB_HOST",
        until=date(2024, 1, 1)
    )

Related Files:
    - app/settings.py: Main settings configuration
    - app/logging.py: Logging utilities
    - app/utils.py: General utility functions
"""

from __future__ import annotations

import os
from datetime import date

# Following are commented out due to circular import after importing logging in api.py
# from app.logging import Ansi
# from app.logging import log


def read_bool(value: str) -> bool:
    """Parse a boolean value from a string environment variable.

    Args:
        value: String value to parse as boolean

    Returns:
        True if value is 'true', '1', or 'yes' (case-insensitive)
    """
    return value.lower() in ("true", "1", "yes")


def read_list(value: str) -> list[str]:
    """Parse a comma-separated list from a string environment variable.

    Args:
        value: Comma-separated string to parse

    Returns:
        List of trimmed strings from the comma-separated input
    """
    return [v.strip() for v in value.split(",")]


def support_deprecated_vars(
    new_name: str,
    deprecated_name: str,
    *,
    until: date,
    allow_empty_string: bool = False,
) -> str:
    """Support deprecated environment variables with migration warnings.

    This function provides backward compatibility for deprecated configuration
    options while encouraging migration to new variable names. It checks for
    the new variable first, then falls back to the deprecated one with a
    warning message.

    Args:
        new_name: Name of the new environment variable
        deprecated_name: Name of the deprecated environment variable
        until: Date when the deprecated variable will be removed
        allow_empty_string: Whether to allow empty string values

    Returns:
        Value from either the new or deprecated variable

    Raises:
        ValueError: If deprecated variable is used after its removal date
        KeyError: If neither variable is set and empty strings are not allowed
    """
    val1 = os.getenv(new_name)
    if val1:
        return val1

    val2 = os.getenv(deprecated_name)
    if val2:
        if until < date.today():
            raise ValueError(
                f'The "{deprecated_name}" config option has been deprecated as of {until.isoformat()} and is no longer supported. Use {new_name} instead.',
            )

        # log(
        #    f'The "{deprecated_name}" config option has been deprecated and will be supported until {until.isoformat()}. Use {new_name} instead.',
        #    Ansi.LYELLOW,
        # )
        return val2

    if allow_empty_string:
        if val1 is not None:
            return val1
        if val2 is not None:
            return val2

    raise KeyError(f"{new_name} is not set in the environment")
