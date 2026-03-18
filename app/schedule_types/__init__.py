"""
Schedule Types Package - Provider Registry and Helper Functions

This package provides a modular, extensible system for managing different types
of season schedules. Each schedule type is implemented as a separate provider
module that implements the ScheduleTypeProvider interface.

The package includes a registry system that allows schedule type providers to
be registered and retrieved by name. This enables the seasons system to work
with any schedule type through a unified interface.

Key Features:
    - Provider registry for schedule type modules
    - Helper functions for retrieving providers
    - Support for multiple schedule types per provider
    - Configuration validation through providers
    - Extensible architecture for custom schedule types

Built-in Schedule Types:
    - manual: Admin-controlled season start/end
    - custom: Configurable interval scheduling
    - seasonal: World seasons (spring, summer, fall, winter)
    - half_year: Two seasons per year
    - third_year: Three seasons per year
    - quarter_year: Four seasons per year (Q1-Q4)
    - ifc_sched: Custom 28-day month calendar system

Integration Points:
    - Base class in app/schedule_types/base.py
    - Seasons repository in app/repositories/seasons.py
    - Background tasks in app/bg_loops.py
    - Season management commands in app/commands.py

Usage Pattern:
    # Get a provider by name
    provider = get_schedule_provider("manual")
    
    # Get provider for a specific schedule type
    provider = get_provider_for_schedule_type("custom")
    
    # Calculate next season
    start, end = provider.calculate_next_season("custom", datetime.now(), config)
    
    # Validate configuration
    is_valid = provider.validate_config("custom", config)

Related Files:
    - app/schedule_types/base.py: ScheduleTypeProvider ABC
    - app/schedule_types/manual.py: Manual schedule provider
    - app/schedule_types/standard_calendar.py: Standard calendar provider
    - app/schedule_types/seasonal.py: World seasons provider
    - app/schedule_types/international_fixed_calendar.py: International Fixed Calendar provider
"""

from __future__ import annotations

from app.schedule_types.base import ScheduleTypeProvider
from app.schedule_types.manual import ManualScheduleProvider
from app.schedule_types.seasonal import SeasonalScheduleProvider
from app.schedule_types.standard_calendar import StandardCalendarProvider
from app.schedule_types.international_fixed_calendar import IFCScheduleProvider

# Registry of all available schedule type providers
SCHEDULE_PROVIDERS: dict[str, type[ScheduleTypeProvider]] = {
    "manual": ManualScheduleProvider,
    "standard_calendar": StandardCalendarProvider,
    "seasonal": SeasonalScheduleProvider,
    "ifc_sched": IFCScheduleProvider,
}


def get_schedule_provider(provider_name: str) -> ScheduleTypeProvider | None:
    """Get a schedule type provider instance by name.
    
    Args:
        provider_name: The name of the provider (e.g., "manual", "standard_calendar")
        
    Returns:
        An instance of the provider, or None if not found
    """
    provider_class = SCHEDULE_PROVIDERS.get(provider_name)
    if provider_class:
        return provider_class()
    return None


def get_provider_for_schedule_type(schedule_type: str) -> ScheduleTypeProvider | None:
    """Get the provider that handles a specific schedule type.
    
    Args:
        schedule_type: The schedule type identifier (e.g., "custom", "half_year")
        
    Returns:
        The provider instance that handles this schedule type, or None if not found
    """
    for provider_class in SCHEDULE_PROVIDERS.values():
        provider = provider_class()
        if schedule_type in provider.schedule_types:
            return provider
    return None


def get_all_schedule_types() -> list[str]:
    """Get a list of all available schedule types across all providers.
    
    Returns:
        A list of all schedule type identifiers
    """
    all_types: list[str] = []
    for provider_class in SCHEDULE_PROVIDERS.values():
        provider = provider_class()
        all_types.extend(provider.schedule_types)
    return all_types


def register_schedule_provider(
    name: str,
    provider_class: type[ScheduleTypeProvider],
) -> None:
    """Register a new schedule type provider.
    
    This function allows custom schedule type providers to be registered
    at runtime, enabling extensibility without modifying core code.
    
    Args:
        name: The name to register the provider under
        provider_class: The provider class to register
    """
    SCHEDULE_PROVIDERS[name] = provider_class


__all__ = [
    "ScheduleTypeProvider",
    "SCHEDULE_PROVIDERS",
    "get_schedule_provider",
    "get_provider_for_schedule_type",
    "get_all_schedule_types",
    "register_schedule_provider",
]
