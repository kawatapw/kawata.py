"""
Typing Utilities Module - Type Definitions and Sentinel Values

This module provides custom type definitions and utility classes for the osu!
server application, including IP address type unions and sentinel values for
optional parameter handling. It serves as a central location for type-related
utilities that are used throughout the codebase.

The module defines common type aliases and sentinel values that help maintain
type safety and provide clear semantics for optional parameters and special
values in function signatures and data structures.

Key Features:
    - IP address type union for IPv4 and IPv6 support
    - Sentinel value for distinguishing unset parameters from None
    - Type variable for generic type hints
    - Copy and serialization support for sentinel values
    - Clean type definitions for use throughout the application

Integration Points:
    - Network operations in app/state/services.py
    - Player geolocation in app/objects/player.py
    - API parameter handling in app/api/
    - Database operations in app/repositories/
    - Configuration management in app/settings.py

Type Definitions:
    - IPAddress: Union of IPv4Address and IPv6Address
    - T: Generic type variable for type hints
    - _UnsetSentinel: Sentinel class for unset parameter detection
    - UNSET: Singleton instance of _UnsetSentinel

Usage Pattern:
    # Use IPAddress for network operations
    from app._typing import IPAddress

    def process_ip(ip: IPAddress) -> None:
        # Handle both IPv4 and IPv6 addresses
        pass

    # Use UNSET for optional parameters
    from app._typing import UNSET

    def update_setting(value: str | None = UNSET) -> None:
        if value is UNSET:
            # Parameter was not provided
            pass
        elif value is None:
            # Parameter was explicitly set to None
            pass
        else:
            # Parameter has a value
            pass

Related Files:
    - app/state/services.py: Network and geolocation services
    - app/objects/player.py: Player data with IP information
    - app/api/: API parameter handling
    - app/settings.py: Configuration with optional parameters
"""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address
from typing import Any, TypeVar

T = TypeVar("T")

IPAddress = IPv4Address | IPv6Address


class _UnsetSentinel:
    """Sentinel class for distinguishing unset parameters from None.

    This class provides a unique sentinel value that can be used to
    distinguish between a parameter that was not provided (UNSET) and
    a parameter that was explicitly set to None.
    """

    def __repr__(self) -> str:
        return "Unset"

    def __copy__(self: T) -> T:
        return self

    def __reduce__(self) -> str:
        return "Unset"

    def __deepcopy__(self: T, _: Any) -> T:
        return self


UNSET = _UnsetSentinel()
