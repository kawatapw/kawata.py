"""
Schedule Type Provider Base Module - Abstract Base Class for Season Schedule Types

This module defines the abstract base class that all schedule type providers must
implement. It provides a common interface for calculating season dates, validating
configurations, and generating season names across different scheduling methods.

The ScheduleTypeProvider ABC ensures consistency across all schedule type modules
and enables the seasons system to work with any schedule type through a unified
interface. Each provider module can implement one or more schedule types.

Key Features:
    - Abstract interface for schedule type providers
    - Common methods for season calculation and validation
    - Support for multiple schedule types per provider
    - Configuration schema validation
    - Season name generation

Integration Points:
    - Schedule type registry in app/schedule_types/__init__.py
    - Seasons repository in app/repositories/seasons.py
    - Background tasks in app/bg_loops.py
    - Season management commands in app/commands.py

Usage Pattern:
    # Implement a custom schedule type provider
    class MyScheduleProvider(ScheduleTypeProvider):
        @property
        def name(self) -> str:
            return "my_schedule"

        @property
        def schedule_types(self) -> list[str]:
            return ["my_type"]

        def calculate_next_season(self, schedule_type, current_time, config):
            # Calculate and return (start_date, end_date)
            pass

        def get_season_name(self, schedule_type, start_date, config):
            # Return human-readable season name
            pass

        def validate_config(self, schedule_type, config):
            # Return True if config is valid
            pass

Related Files:
    - app/schedule_types/__init__.py: Provider registry
    - app/schedule_types/manual.py: Manual schedule provider
    - app/schedule_types/standard_calendar.py: Standard calendar provider
    - app/schedule_types/seasonal.py: World seasons provider
    - app/schedule_types/international_fixed_calendar.py: International Fixed Calendar provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class ScheduleTypeProvider(ABC):
    """Base class for schedule type provider modules.

    All schedule type providers must implement this interface to be registered
    with the seasons system. Providers can implement one or more schedule types.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider module.

        Returns:
            A string identifier for this provider (e.g., "manual", "standard_calendar")
        """
        ...

    @property
    @abstractmethod
    def schedule_types(self) -> list[str]:
        """List of schedule type identifiers this module provides.

        Returns:
            A list of schedule type strings this provider handles
            (e.g., ["custom", "half_year", "third_year", "quarter_year"])
        """
        ...

    @abstractmethod
    def get_config_schema(self, schedule_type: str) -> dict[str, Any]:
        """Get the JSON schema for a specific schedule type.

        Args:
            schedule_type: The schedule type identifier

        Returns:
            JSON schema dict for the schedule type configuration
        """
        ...

    @abstractmethod
    def calculate_next_season(
        self,
        schedule_type: str,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate the start and end dates for the next season.

        Args:
            schedule_type: The schedule type identifier
            current_time: The current datetime
            config: The schedule configuration from the database

        Returns:
            A tuple of (start_date, end_date) for the next season
        """
        ...

    @abstractmethod
    def get_season_name(
        self,
        schedule_type: str,
        start_date: datetime,
        config: dict[str, Any],
    ) -> str:
        """Generate a name for the season based on its start date.

        Args:
            schedule_type: The schedule type identifier
            start_date: The start date of the season
            config: The schedule configuration from the database

        Returns:
            A human-readable name for the season (e.g., "Spring 2024")
        """
        ...

    @abstractmethod
    def validate_config(
        self,
        schedule_type: str,
        config: dict[str, Any],
    ) -> bool:
        """Validate the schedule configuration.

        Args:
            schedule_type: The schedule type identifier
            config: The schedule configuration to validate

        Returns:
            True if the configuration is valid, False otherwise
        """
        ...

    @abstractmethod
    def calculate_seasons_for_range(
        self,
        schedule_type: str,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all seasons within a date range.

        This method is used for retroactive season creation. It should generate
        all seasons that would have occurred between start_date and end_date
        based on the schedule type's rules.

        Args:
            schedule_type: The schedule type identifier
            start_date: The start of the date range (oldest score time)
            end_date: The end of the date range (current time)
            config: The schedule configuration from the database

        Returns:
            A list of (start_date, end_date) tuples for each season in the range,
            ordered from oldest to newest.
        """
        ...
