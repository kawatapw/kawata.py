"""
Manual Schedule Provider - Admin-Controlled Season Management

This module provides manual season management with no automatic scheduling.
Seasons are started and ended manually by administrators through commands
or API endpoints.

Schedule Types Provided:
    - manual: Admin manually starts/ends seasons

Configuration Schema:
    {
        "type": "manual"
    }

Features:
    - No automatic scheduling
    - Admin controls season start/end via commands
    - Simplest schedule type with minimal configuration
    - Suitable for servers that want full control over season timing

Integration Points:
    - Base class in app/schedule_types/base.py
    - Seasons repository in app/repositories/seasons.py
    - Season management commands in app/commands.py

Usage Pattern:
    # Get the manual provider
    provider = ManualScheduleProvider()

    # Validate configuration
    is_valid = provider.validate_config("manual", {})

    # Get season name
    name = provider.get_season_name("manual", datetime.now(), {})

Related Files:
    - app/schedule_types/base.py: ScheduleTypeProvider ABC
    - app/schedule_types/__init__.py: Provider registry
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schedule_types.base import ScheduleTypeProvider


class ManualScheduleProvider(ScheduleTypeProvider):
    """Provider for manual season management.

    This provider implements manual season scheduling where administrators
    have full control over when seasons start and end. No automatic
    scheduling is performed.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this provider module."""
        return "manual"

    @property
    def schedule_types(self) -> list[str]:
        """List of schedule type identifiers this module provides."""
        return ["manual"]

    def get_config_schema(self, schedule_type: str) -> dict[str, Any]:
        """Get the JSON schema for manual schedule type.

        Args:
            schedule_type: The schedule type identifier (should be "manual")

        Returns:
            JSON schema dict for the manual schedule type configuration
        """
        return {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["manual"],
                    "description": "Schedule type identifier",
                },
            },
            "required": ["type"],
        }

    def calculate_next_season(
        self,
        schedule_type: str,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate the start and end dates for the next season.

        For manual scheduling, this method is not used as seasons are
        created manually by administrators. This method raises an error
        to indicate that manual scheduling doesn't support automatic
        season calculation.

        Args:
            schedule_type: The schedule type identifier (should be "manual")
            current_time: The current datetime
            config: The schedule configuration from the database

        Raises:
            NotImplementedError: Manual scheduling doesn't support automatic calculation
        """
        raise NotImplementedError(
            "Manual scheduling does not support automatic season calculation. "
            "Seasons must be created manually by administrators.",
        )

    def get_season_name(
        self,
        schedule_type: str,
        start_date: datetime,
        config: dict[str, Any],
    ) -> str:
        """Generate a name for the season based on its start date.

        For manual scheduling, generates a simple name based on the start date.

        Args:
            schedule_type: The schedule type identifier (should be "manual")
            start_date: The start date of the season
            config: The schedule configuration from the database

        Returns:
            A human-readable name for the season (e.g., "Season 2024-03-15")
        """
        return f"Season {start_date.strftime('%Y-%m-%d')}"

    def validate_config(
        self,
        schedule_type: str,
        config: dict[str, Any],
    ) -> bool:
        """Validate the schedule configuration.

        For manual scheduling, the configuration is minimal and always valid
        as long as the schedule_type is "manual".

        Args:
            schedule_type: The schedule type identifier (should be "manual")
            config: The schedule configuration to validate

        Returns:
            True if the configuration is valid, False otherwise
        """
        return schedule_type == "manual"

    def calculate_seasons_for_range(
        self,
        schedule_type: str,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all seasons within a date range for manual schedule.

        For manual scheduling, this method returns an empty list as seasons
        are created manually by administrators and cannot be automatically
        calculated for a date range.

        Args:
            schedule_type: The schedule type identifier (should be "manual")
            start_date: The start of the date range (oldest score time)
            end_date: The end of the date range (current time)
            config: The schedule configuration from the database

        Returns:
            An empty list as manual scheduling doesn't support automatic calculation
        """
        return []
