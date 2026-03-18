"""
Standard Calendar Schedule Provider - Gregorian Calendar-Based Scheduling

This module provides scheduling methods based on the standard Gregorian calendar.
It handles multiple scheduling patterns including custom intervals, half-year,
third-year, and quarter-year seasons.

Schedule Types Provided:
    - custom: Configurable interval with flexible units (days, weeks, months)
    - half_year: 2 seasons per year (January-June, July-December)
    - third_year: 3 seasons per year (January-April, May-August, September-December)
    - quarter_year: 4 seasons per year (Q1, Q2, Q3, Q4)

Configuration Schemas:
    Custom:
    {
        "schedule_type": "custom",
        "interval": {
            "value": 30,
            "unit": "days"
        },
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z",
        "auto_start": true,
        "auto_end": true
    }
    
    Half Year:
    {
        "schedule_type": "half_year",
        "start_month": 1,
        "timezone": "UTC"
    }
    
    Third Year:
    {
        "schedule_type": "third_year",
        "start_month": 1,
        "timezone": "UTC"
    }
    
    Quarter Year:
    {
        "schedule_type": "quarter_year",
        "start_month": 1,
        "timezone": "UTC"
    }

Features:
    - Provides multiple scheduling methods in a single module
    - Handles all standard calendar-based date calculations
    - Supports configurable start months for alignment
    - Timezone-aware date calculations
    - Flexible interval configuration (days, weeks, months)

Integration Points:
    - Base class in app/schedule_types/base.py
    - Seasons repository in app/repositories/seasons.py
    - Background tasks in app/bg_loops.py

Usage Pattern:
    # Get the standard calendar provider
    provider = StandardCalendarProvider()
    
    # Calculate next custom season
    start, end = provider.calculate_next_season("custom", datetime.now(), config)
    
    # Get season name
    name = provider.get_season_name("half_year", datetime.now(), config)

Related Files:
    - app/schedule_types/base.py: ScheduleTypeProvider ABC
    - app/schedule_types/__init__.py: Provider registry
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.schedule_types.base import ScheduleTypeProvider


class StandardCalendarProvider(ScheduleTypeProvider):
    """Provider for standard Gregorian calendar-based scheduling.
    
    This provider implements multiple scheduling methods based on the
    standard Gregorian calendar, including custom intervals and fixed
    period divisions (half-year, third-year, quarter-year).
    """

    @property
    def name(self) -> str:
        """Unique identifier for this provider module."""
        return "standard_calendar"

    @property
    def schedule_types(self) -> list[str]:
        """List of schedule type identifiers this module provides."""
        return ["custom", "half_year", "third_year", "quarter_year"]

    def get_config_schema(self, schedule_type: str) -> dict[str, Any]:
        """Get the JSON schema for a specific schedule type.
        
        Args:
            schedule_type: The schedule type identifier
            
        Returns:
            JSON schema dict for the schedule type configuration
        """
        schemas = {
            "custom": {
                "type": "object",
                "properties": {
                    "schedule_type": {
                        "type": "string",
                        "enum": ["custom"],
                    },
                    "interval": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "integer", "minimum": 1},
                            "unit": {
                                "type": "string",
                                "enum": ["days", "weeks", "months"],
                            },
                        },
                        "required": ["value", "unit"],
                    },
                    "start_date": {"type": "string", "format": "date-time"},
                    "end_date": {"type": "string", "format": "date-time"},
                    "auto_start": {"type": "boolean"},
                    "auto_end": {"type": "boolean"},
                },
                "required": ["schedule_type", "interval"],
            },
            "half_year": {
                "type": "object",
                "properties": {
                    "schedule_type": {
                        "type": "string",
                        "enum": ["half_year"],
                    },
                    "start_month": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 12,
                    },
                    "timezone": {"type": "string"},
                },
                "required": ["schedule_type"],
            },
            "third_year": {
                "type": "object",
                "properties": {
                    "schedule_type": {
                        "type": "string",
                        "enum": ["third_year"],
                    },
                    "start_month": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 12,
                    },
                    "timezone": {"type": "string"},
                },
                "required": ["schedule_type"],
            },
            "quarter_year": {
                "type": "object",
                "properties": {
                    "schedule_type": {
                        "type": "string",
                        "enum": ["quarter_year"],
                    },
                    "start_month": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 12,
                    },
                    "timezone": {"type": "string"},
                },
                "required": ["schedule_type"],
            },
        }
        return schemas.get(schedule_type, {})

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
        if schedule_type == "custom":
            return self._calculate_custom_season(current_time, config)
        elif schedule_type == "half_year":
            return self._calculate_half_year_season(current_time, config)
        elif schedule_type == "third_year":
            return self._calculate_third_year_season(current_time, config)
        elif schedule_type == "quarter_year":
            return self._calculate_quarter_year_season(current_time, config)
        else:
            raise ValueError(f"Unknown schedule type: {schedule_type}")

    def _calculate_custom_season(
        self,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate next season for custom interval scheduling."""
        interval = config.get("interval", {"value": 30, "unit": "days"})
        value = interval.get("value", 30)
        unit = interval.get("unit", "days")
        
        if unit == "days":
            delta = timedelta(days=value)
        elif unit == "weeks":
            delta = timedelta(weeks=value)
        elif unit == "months":
            # Approximate months as 30 days
            delta = timedelta(days=value * 30)
        else:
            delta = timedelta(days=30)
        
        start_date = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + delta
        
        return start_date, end_date

    def _calculate_half_year_season(
        self,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate next season for half-year scheduling (2 seasons per year)."""
        start_month = config.get("start_month", 1)
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        current_time = current_time.astimezone(tz)
        year = current_time.year
        month = current_time.month
        
        # Determine which half of the year we're in
        if month < 7:
            # First half: start_month to June
            start_date = datetime(year, start_month, 1, tzinfo=tz)
            end_date = datetime(year, 7, 1, tzinfo=tz)
        else:
            # Second half: July to December
            start_date = datetime(year, 7, 1, tzinfo=tz)
            end_date = datetime(year + 1, start_month, 1, tzinfo=tz)
        
        # If current time is past the end date, calculate next season
        if current_time >= end_date:
            if month >= 7:
                start_date = datetime(year + 1, start_month, 1, tzinfo=tz)
                end_date = datetime(year + 1, 7, 1, tzinfo=tz)
            else:
                start_date = datetime(year, 7, 1, tzinfo=tz)
                end_date = datetime(year + 1, start_month, 1, tzinfo=tz)
        
        return start_date, end_date

    def _calculate_third_year_season(
        self,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate next season for third-year scheduling (3 seasons per year)."""
        start_month = config.get("start_month", 1)
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        current_time = current_time.astimezone(tz)
        year = current_time.year
        month = current_time.month
        
        # Define season boundaries (4 months each)
        season_starts = [
            (start_month, f"{year}-{start_month:02d}-01"),
            ((start_month + 4 - 1) % 12 + 1, f"{year}-{(start_month + 4 - 1) % 12 + 1:02d}-01"),
            ((start_month + 8 - 1) % 12 + 1, f"{year}-{(start_month + 8 - 1) % 12 + 1:02d}-01"),
        ]
        
        # Find current season
        for i, (start_m, _) in enumerate(season_starts):
            end_m = season_starts[(i + 1) % 3][0]
            if start_m <= month < end_m or (start_m > end_m and (month >= start_m or month < end_m)):
                start_date = datetime(year, start_m, 1, tzinfo=tz)
                if end_m > start_m:
                    end_date = datetime(year, end_m, 1, tzinfo=tz)
                else:
                    end_date = datetime(year + 1, end_m, 1, tzinfo=tz)
                break
        else:
            # Default to first season
            start_date = datetime(year, start_month, 1, tzinfo=tz)
            end_date = datetime(year, start_month + 4, 1, tzinfo=tz)
        
        # If current time is past the end date, calculate next season
        if current_time >= end_date:
            start_date = end_date
            end_month = (end_date.month + 4 - 1) % 12 + 1
            if end_month > end_date.month:
                end_date = datetime(year, end_month, 1, tzinfo=tz)
            else:
                end_date = datetime(year + 1, end_month, 1, tzinfo=tz)
        
        return start_date, end_date

    def _calculate_quarter_year_season(
        self,
        current_time: datetime,
        config: dict[str, Any],
    ) -> tuple[datetime, datetime]:
        """Calculate next season for quarter-year scheduling (4 seasons per year)."""
        start_month = config.get("start_month", 1)
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        current_time = current_time.astimezone(tz)
        year = current_time.year
        month = current_time.month
        
        # Define quarter boundaries
        quarters = [
            (start_month, (start_month + 3 - 1) % 12 + 1),
            ((start_month + 3 - 1) % 12 + 1, (start_month + 6 - 1) % 12 + 1),
            ((start_month + 6 - 1) % 12 + 1, (start_month + 9 - 1) % 12 + 1),
            ((start_month + 9 - 1) % 12 + 1, start_month),
        ]
        
        # Find current quarter
        for i, (start_m, end_m) in enumerate(quarters):
            if start_m <= month < end_m or (start_m > end_m and (month >= start_m or month < end_m)):
                start_date = datetime(year, start_m, 1, tzinfo=tz)
                if end_m > start_m:
                    end_date = datetime(year, end_m, 1, tzinfo=tz)
                else:
                    end_date = datetime(year + 1, end_m, 1, tzinfo=tz)
                break
        else:
            # Default to first quarter
            start_date = datetime(year, start_month, 1, tzinfo=tz)
            end_date = datetime(year, start_month + 3, 1, tzinfo=tz)
        
        # If current time is past the end date, calculate next quarter
        if current_time >= end_date:
            start_date = end_date
            end_month = (end_date.month + 3 - 1) % 12 + 1
            if end_month > end_date.month:
                end_date = datetime(year, end_month, 1, tzinfo=tz)
            else:
                end_date = datetime(year + 1, end_month, 1, tzinfo=tz)
        
        return start_date, end_date

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
            A human-readable name for the season in format SC-{YEAR}-{TYPE}{SEASON}
        """
        year = start_date.year
        
        if schedule_type == "custom":
            # For custom, use day of year to determine season number
            day_of_year = start_date.timetuple().tm_yday
            season = (day_of_year - 1) // 30 + 1  # Approximate 30-day periods
            return f"SC-{year}-C{season}"
        elif schedule_type == "half_year":
            season = 1 if start_date.month < 7 else 2
            return f"SC-{year}-H{season}"
        elif schedule_type == "third_year":
            season = (start_date.month - 1) // 4 + 1
            return f"SC-{year}-T{season}"
        elif schedule_type == "quarter_year":
            season = (start_date.month - 1) // 3 + 1
            return f"SC-{year}-Q{season}"
        else:
            return f"SC-{year}-{start_date.strftime('%m%d')}"

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
        if schedule_type not in self.schedule_types:
            return False
        
        if schedule_type == "custom":
            interval = config.get("interval")
            if not interval:
                return False
            if "value" not in interval or "unit" not in interval:
                return False
            if interval["unit"] not in ("days", "weeks", "months"):
                return False
            if not isinstance(interval["value"], int) or interval["value"] < 1:
                return False
        
        return True

    def calculate_seasons_for_range(
        self,
        schedule_type: str,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all seasons within a date range for standard calendar.
        
        This method generates all seasons that would have occurred between start_date
        and end_date based on the schedule type's rules.
        
        Args:
            schedule_type: The schedule type identifier
            start_date: The start of the date range (oldest score time)
            end_date: The end of the date range (current time)
            config: The schedule configuration from the database
            
        Returns:
            A list of (start_date, end_date) tuples for each season in the range,
            ordered from oldest to newest.
        """
        if schedule_type == "custom":
            return self._calculate_custom_seasons_for_range(start_date, end_date, config)
        elif schedule_type == "half_year":
            return self._calculate_half_year_seasons_for_range(start_date, end_date, config)
        elif schedule_type == "third_year":
            return self._calculate_third_year_seasons_for_range(start_date, end_date, config)
        elif schedule_type == "quarter_year":
            return self._calculate_quarter_year_seasons_for_range(start_date, end_date, config)
        else:
            return []

    def _calculate_custom_seasons_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all custom interval seasons within a date range."""
        interval = config.get("interval", {"value": 30, "unit": "days"})
        value = interval.get("value", 30)
        unit = interval.get("unit", "days")
        
        if unit == "days":
            delta = timedelta(days=value)
        elif unit == "weeks":
            delta = timedelta(weeks=value)
        elif unit == "months":
            # Approximate months as 30 days
            delta = timedelta(days=value * 30)
        else:
            delta = timedelta(days=30)
        
        seasons = []
        current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current < end_date:
            season_end = current + delta
            if season_end > start_date and current < end_date:
                seasons.append((current, season_end))
            current = season_end
        
        return seasons

    def _calculate_half_year_seasons_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all half-year seasons within a date range."""
        start_month = config.get("start_month", 1)
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        start_date = start_date.astimezone(tz)
        end_date = end_date.astimezone(tz)
        
        seasons = []
        current_year = start_date.year
        
        while True:
            # First half: start_month to June
            season1_start = datetime(current_year, start_month, 1, tzinfo=tz)
            season1_end = datetime(current_year, 7, 1, tzinfo=tz)
            
            # Second half: July to December
            season2_start = datetime(current_year, 7, 1, tzinfo=tz)
            season2_end = datetime(current_year + 1, start_month, 1, tzinfo=tz)
            
            # Add seasons that overlap with our range
            if season1_start < end_date and season1_end > start_date:
                seasons.append((season1_start, season1_end))
            if season2_start < end_date and season2_end > start_date:
                seasons.append((season2_start, season2_end))
            
            current_year += 1
            
            # Stop if we've passed the end date
            if datetime(current_year, 1, 1, tzinfo=tz) >= end_date:
                break
        
        return seasons

    def _calculate_third_year_seasons_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all third-year seasons within a date range."""
        start_month = config.get("start_month", 1)
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        start_date = start_date.astimezone(tz)
        end_date = end_date.astimezone(tz)
        
        seasons = []
        current_year = start_date.year
        
        while True:
            # Define season boundaries (4 months each)
            season_starts = [
                (start_month, f"{current_year}-{start_month:02d}-01"),
                ((start_month + 4 - 1) % 12 + 1, f"{current_year}-{(start_month + 4 - 1) % 12 + 1:02d}-01"),
                ((start_month + 8 - 1) % 12 + 1, f"{current_year}-{(start_month + 8 - 1) % 12 + 1:02d}-01"),
            ]
            
            for i, (start_m, _) in enumerate(season_starts):
                end_m = season_starts[(i + 1) % 3][0]
                season_start = datetime(current_year, start_m, 1, tzinfo=tz)
                if end_m > start_m:
                    season_end = datetime(current_year, end_m, 1, tzinfo=tz)
                else:
                    season_end = datetime(current_year + 1, end_m, 1, tzinfo=tz)
                
                if season_start < end_date and season_end > start_date:
                    seasons.append((season_start, season_end))
            
            current_year += 1
            
            # Stop if we've passed the end date
            if datetime(current_year, 1, 1, tzinfo=tz) >= end_date:
                break
        
        return seasons

    def _calculate_quarter_year_seasons_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all quarter-year seasons within a date range."""
        start_month = config.get("start_month", 1)
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        start_date = start_date.astimezone(tz)
        end_date = end_date.astimezone(tz)
        
        seasons = []
        current_year = start_date.year
        
        while True:
            # Define quarter boundaries
            quarters = [
                (start_month, (start_month + 3 - 1) % 12 + 1),
                ((start_month + 3 - 1) % 12 + 1, (start_month + 6 - 1) % 12 + 1),
                ((start_month + 6 - 1) % 12 + 1, (start_month + 9 - 1) % 12 + 1),
                ((start_month + 9 - 1) % 12 + 1, start_month),
            ]
            
            for i, (start_m, end_m) in enumerate(quarters):
                season_start = datetime(current_year, start_m, 1, tzinfo=tz)
                if end_m > start_m:
                    season_end = datetime(current_year, end_m, 1, tzinfo=tz)
                else:
                    season_end = datetime(current_year + 1, end_m, 1, tzinfo=tz)
                
                if season_start < end_date and season_end > start_date:
                    seasons.append((season_start, season_end))
            
            current_year += 1
            
            # Stop if we've passed the end date
            if datetime(current_year, 1, 1, tzinfo=tz) >= end_date:
                break
        
        return seasons
