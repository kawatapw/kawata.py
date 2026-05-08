"""
Seasonal Schedule Provider - World Seasons Based on Astronomical Events

This module provides scheduling based on astronomical world seasons (spring,
summer, fall, winter). It calculates season dates based on equinoxes and
solstices, supporting both Northern and Southern hemispheres.

Schedule Types Provided:
    - seasonal: World seasons based on equinoxes and solstices

Configuration Schema:
    {
        "timezone": "UTC",
        "hemisphere": "northern"
    }

Season Definitions (Northern Hemisphere):
    - Spring: March 20 - June 20
    - Summer: June 21 - September 22
    - Fall: September 23 - December 20
    - Winter: December 21 - March 19

Season Definitions (Southern Hemisphere):
    - Spring: September 23 - December 20
    - Summer: December 21 - March 19
    - Fall: March 20 - June 20
    - Winter: June 21 - September 22

Features:
    - Calculates season dates based on astronomical events
    - Supports both Northern and Southern hemispheres
    - Timezone-aware date calculations
    - Automatic season name generation (e.g., "Spring 2024")

Integration Points:
    - Base class in app/schedule_types/base.py
    - Seasons repository in app/repositories/seasons.py
    - Background tasks in app/bg_loops.py

Usage Pattern:
    # Get the seasonal provider
    provider = SeasonalScheduleProvider()

    # Calculate next season
    start, end = provider.calculate_next_season("seasonal", datetime.now(), config)

    # Get season name
    name = provider.get_season_name("seasonal", datetime.now(), config)

Related Files:
    - app/schedule_types/base.py: ScheduleTypeProvider ABC
    - app/schedule_types/__init__.py: Provider registry
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.schedule_types.base import ScheduleTypeProvider

# Approximate astronomical season dates (Northern Hemisphere)
# These are based on typical equinox/solstice dates
NORTHERN_SEASONS = [
    # (name, start_month, start_day, end_month, end_day)
    ("Spring", 3, 20, 6, 20),
    ("Summer", 6, 21, 9, 22),
    ("Fall", 9, 23, 12, 20),
    ("Winter", 12, 21, 3, 19),
]

# Southern Hemisphere has opposite seasons
SOUTHERN_SEASONS = [
    ("Fall", 3, 20, 6, 20),
    ("Winter", 6, 21, 9, 22),
    ("Spring", 9, 23, 12, 20),
    ("Summer", 12, 21, 3, 19),
]


class SeasonalScheduleProvider(ScheduleTypeProvider):
    """Provider for world seasons based on astronomical events.

    This provider implements scheduling based on the four astronomical
    seasons (spring, summer, fall, winter) determined by equinoxes
    and solstices.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this provider module."""
        return "seasonal"

    @property
    def schedule_types(self) -> list[str]:
        """List of schedule type identifiers this module provides."""
        return ["seasonal"]

    def get_config_schema(self, schedule_type: str) -> dict[str, Any]:
        """Get the JSON schema for seasonal schedule type.

        Args:
            schedule_type: The schedule type identifier (should be "seasonal")

        Returns:
            JSON schema dict for the seasonal schedule type configuration
        """
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone for date calculations",
                    "default": "UTC",
                },
                "hemisphere": {
                    "type": "string",
                    "enum": ["northern", "southern"],
                    "description": "Hemisphere for season definitions",
                    "default": "northern",
                },
            },
            "required": [],
        }

    def calculate_next_season(
        self,
        schedule_type: str,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate the start and end dates for the next season.

        Args:
            schedule_type: The schedule type identifier (should be "seasonal")
            current_time: The current datetime
            config: The schedule configuration from the database

        Returns:
            A tuple of (start_date, end_date) for the next season
        """
        tz_name = config.get("timezone", "UTC")
        hemisphere = config.get("hemisphere", "northern")
        tz = ZoneInfo(tz_name)

        current_time = current_time.astimezone(tz)
        year = current_time.year

        seasons = NORTHERN_SEASONS if hemisphere == "northern" else SOUTHERN_SEASONS

        # Find current or next season
        for _, start_m, start_d, end_m, end_d in seasons:
            # Handle year wrap-around for winter
            if start_m > end_m:
                # Season spans year boundary (e.g., Winter: Dec 21 - Mar 19)
                if current_time.month >= start_m or current_time.month < end_m:
                    start_date = datetime(year, start_m, start_d, tzinfo=tz)
                    if current_time.month >= start_m:
                        end_date = datetime(year + 1, end_m, end_d, tzinfo=tz)
                    else:
                        end_date = datetime(year, end_m, end_d, tzinfo=tz)

                    if current_time < end_date:
                        return start_date, end_date
            else:
                # Normal season within same year
                start_date = datetime(year, start_m, start_d, tzinfo=tz)
                end_date = datetime(year, end_m, end_d, tzinfo=tz)

                if start_date <= current_time < end_date:
                    return start_date, end_date

        # If we get here, find the next season
        for _, start_m, start_d, end_m, end_d in seasons:
            if start_m > end_m:
                # Year boundary season
                if current_time.month < start_m:
                    start_date = datetime(year, start_m, start_d, tzinfo=tz)
                    end_date = datetime(year + 1, end_m, end_d, tzinfo=tz)
                    return start_date, end_date
            else:
                start_date = datetime(year, start_m, start_d, tzinfo=tz)
                if current_time < start_date:
                    end_date = datetime(year, end_m, end_d, tzinfo=tz)
                    return start_date, end_date

        # Default to next year's spring
        start_date = datetime(year + 1, 3, 20, tzinfo=tz)
        end_date = datetime(year + 1, 6, 20, tzinfo=tz)
        return start_date, end_date

    def get_season_name(
        self,
        schedule_type: str,
        start_date: datetime,
        config: dict[str, Any],
    ) -> str:
        """Generate a name for the season based on its start date.

        Args:
            schedule_type: The schedule type identifier (should be "seasonal")
            start_date: The start date of the season
            config: The schedule configuration from the database

        Returns:
            A human-readable name for the season (e.g., "Spring 2024")
        """
        hemisphere = config.get("hemisphere", "northern")
        seasons = NORTHERN_SEASONS if hemisphere == "northern" else SOUTHERN_SEASONS

        month = start_date.month
        day = start_date.day

        for name, start_m, start_d, _, _ in seasons:
            if start_m == month and start_d == day:
                return f"{name} {start_date.year}"

        # Fallback
        return f"Season {start_date.strftime('%Y-%m-%d')}"

    def validate_config(
        self,
        schedule_type: str,
        config: dict[str, Any],
    ) -> bool:
        """Validate the schedule configuration.

        Args:
            schedule_type: The schedule type identifier (should be "seasonal")
            config: The schedule configuration to validate

        Returns:
            True if the configuration is valid, False otherwise
        """
        if schedule_type != "seasonal":
            return False

        hemisphere = config.get("hemisphere", "northern")
        return hemisphere in ("northern", "southern")

    def calculate_seasons_for_range(
        self,
        schedule_type: str,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all seasons within a date range for seasonal schedule.

        This method generates all seasons that would have occurred between start_date
        and end_date based on the seasonal schedule type's rules.

        Args:
            schedule_type: The schedule type identifier (should be "seasonal")
            start_date: The start of the date range (oldest score time)
            end_date: The end of the date range (current time)
            config: The schedule configuration from the database

        Returns:
            A list of (start_date, end_date) tuples for each season in the range,
            ordered from oldest to newest.
        """
        if schedule_type != "seasonal":
            return []

        tz_name = config.get("timezone", "UTC")
        hemisphere = config.get("hemisphere", "northern")
        tz = ZoneInfo(tz_name)

        start_date = start_date.astimezone(tz)
        end_date = end_date.astimezone(tz)

        seasons = NORTHERN_SEASONS if hemisphere == "northern" else SOUTHERN_SEASONS

        result = []
        current_year = start_date.year

        while True:
            for _name, start_m, start_d, end_m, end_d in seasons:
                # Handle year wrap-around for winter
                if start_m > end_m:
                    # Season spans year boundary (e.g., Winter: Dec 21 - Mar 19)
                    season_start = datetime(current_year, start_m, start_d, tzinfo=tz)
                    season_end = datetime(current_year + 1, end_m, end_d, tzinfo=tz)
                else:
                    # Normal season within same year
                    season_start = datetime(current_year, start_m, start_d, tzinfo=tz)
                    season_end = datetime(current_year, end_m, end_d, tzinfo=tz)

                # Only add if the season overlaps with our range
                if season_start < end_date and season_end > start_date:
                    result.append((season_start, season_end))

            current_year += 1

            # Stop if we've passed the end date
            if datetime(current_year, 1, 1, tzinfo=tz) >= end_date:
                break

        return result
