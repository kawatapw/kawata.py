"""
International Fixed Calendar Schedule Provider - Custom 28-Day Month Calendar System

This module provides scheduling based on a custom 28-day month calendar system.
It handles the complex logic of calculating season dates based on a non-standard
calendar with 13 months of 28 days each, plus a special New Year's Day.

Schedule Types Provided:
    - ifc_sched: Custom 28-day month calendar system

Configuration Schema:
    {
        "month_length": 28,
        "months_per_season": 4,
        "special_month": 13,
        "new_years_day": true,
        "timezone": "UTC"
    }

Calendar Structure:
    - 13 months of 28 days = 364 days
    - New Year's Day is separate (day 365)
    - Seasons: Every 4 months (3 seasons of 4 months + 1 special month)
    - New Year's Day: 1-day special seasonal event (top 3 players get badge)

Features:
    - Calculates season dates based on 28-day month structure
    - Handles the special 13th month
    - Manages New Year's Day as a special event
    - Timezone-aware date calculations
    - Configurable month length and seasons per year

Integration Points:
    - Base class in app/schedule_types/base.py
    - Seasons repository in app/repositories/seasons.py
    - Background tasks in app/bg_loops.py

Usage Pattern:
    # Get the International Fixed Calendar provider
    provider = IFCScheduleProvider()
    
    # Calculate next season
    start, end = provider.calculate_next_season("ifc_sched", datetime.now(), config)
    
    # Get season name
    name = provider.get_season_name("ifc_sched", datetime.now(), config)

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


class IFCScheduleProvider(ScheduleTypeProvider):
    """Provider for International Fixed Calendar system scheduling.
    
    This provider implements scheduling based on a custom calendar with
    13 months of 28 days each, plus a special New Year's Day.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this provider module."""
        return "ifc_sched"

    @property
    def schedule_types(self) -> list[str]:
        """List of schedule type identifiers this module provides."""
        return ["ifc_sched"]

    def get_config_schema(self, schedule_type: str) -> dict[str, Any]:
        """Get the JSON schema for International Fixed Calendar schedule type.
        
        Args:
            schedule_type: The schedule type identifier (should be "ifc_sched")
            
        Returns:
            JSON schema dict for the International Fixed Calendar schedule type configuration
        """
        return {
            "type": "object",
            "properties": {
                "month_length": {
                    "type": "integer",
                    "description": "Length of each month in days",
                    "default": 28,
                },
                "months_per_season": {
                    "type": "integer",
                    "description": "Number of months per season",
                    "default": 4,
                },
                "special_month": {
                    "type": "integer",
                    "description": "Month number for the special 13th month",
                    "default": 13,
                },
                "new_years_day": {
                    "type": "boolean",
                    "description": "Whether to include New Year's Day as a special event",
                    "default": True,
                },
                "timezone": {
                    "type": "string",
                    "description": "Timezone for date calculations",
                    "default": "UTC",
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
        """Calculate the start and end dates for the current season.
        
        Args:
            schedule_type: The schedule type identifier (should be "ifc_sched")
            current_time: The current datetime
            config: The schedule configuration from the database
            
        Returns:
            A tuple of (start_date, end_date) for the current season
        """
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        current_time = current_time.astimezone(tz)
        
        month_length = config.get("month_length", 28)
        months_per_season = config.get("months_per_season", 4)
        special_month = config.get("special_month", 13)
        new_years_day = config.get("new_years_day", True)
        
        # Handle New Year's Day (January 1st) as a special 1-day season
        if new_years_day and current_time.month == 1 and current_time.day == 1:
            start_date = datetime(current_time.year, 1, 1, tzinfo=tz)
            end_date = datetime(current_time.year, 1, 2, tzinfo=tz)
            return start_date, end_date
        
        # Calculate the epoch (start of the International Fixed Calendar)
        # We'll use January 2 of the current year as the epoch
        # (January 1 is New Year's Day, which is its own 1-day season)
        epoch = datetime(current_time.year, 1, 2, tzinfo=tz)
        
        # Calculate days since epoch
        days_since_epoch = (current_time - epoch).days
        
        # Adjust for New Year's Day if it has passed in the current year
        if new_years_day and days_since_epoch >= 364:
            days_since_epoch -= 1
        
        # Calculate current month (1-13)
        current_month = (days_since_epoch // month_length) + 1
        
        # Calculate current season (0-indexed)
        current_season = (current_month - 1) // months_per_season
        
        # Calculate current season's start month
        season_start_month = current_season * months_per_season + 1
        
        # Calculate current season's end month
        # S4 is a special single-month season (month 13 only)
        if current_season == 3:  # S4 (0-indexed, so current_season 3)
            season_end_month = season_start_month  # Only month 13
        else:
            season_end_month = season_start_month + months_per_season - 1
        
        # Calculate days to season start
        days_to_season_start = (season_start_month - 1) * month_length
        if new_years_day and days_to_season_start >= 364:
            days_to_season_start += 1
        
        # Calculate days to season end
        days_to_season_end = season_end_month * month_length
        if new_years_day and days_to_season_end >= 364:
            days_to_season_end += 1
        
        start_date = epoch + timedelta(days=days_to_season_start)
        end_date = epoch + timedelta(days=days_to_season_end)
        
        return start_date, end_date

    def get_season_name(
        self,
        schedule_type: str,
        start_date: datetime,
        config: dict[str, Any],
    ) -> str:
        """Generate a name for the season based on its start date.
        
        Args:
            schedule_type: The schedule type identifier (should be "ifc_sched")
            start_date: The start date of the season
            config: The schedule configuration from the database
            
        Returns:
            A human-readable name for the season
        """
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        start_date = start_date.astimezone(tz)
        
        month_length = config.get("month_length", 28)
        months_per_season = config.get("months_per_season", 4)
        new_years_day = config.get("new_years_day", True)
        
        # Handle New Year's Day (January 1st) as a special season
        if new_years_day and start_date.month == 1 and start_date.day == 1:
            return f"IFC-{start_date.year}-NY"
        
        # Calculate epoch
        # January 2 is the start of the calendar (January 1 is New Year's Day)
        epoch = datetime(start_date.year, 1, 2, tzinfo=tz)
        
        # Calculate days since epoch
        days_since_epoch = (start_date - epoch).days
        
        # Calculate month and season (0-indexed)
        month = (days_since_epoch // month_length) + 1
        season = (month - 1) // months_per_season
        
        # Use S1, S2, S3, S4 format for seasons
        # S1-S3 are regular seasons, S4 is the special 13th month season
        return f"IFC-{start_date.year}-S{season + 1}"

    def validate_config(
        self,
        schedule_type: str,
        config: dict[str, Any],
    ) -> bool:
        """Validate the schedule configuration.
        
        Args:
            schedule_type: The schedule type identifier (should be "ifc_sched")
            config: The schedule configuration to validate
            
        Returns:
            True if the configuration is valid, False otherwise
        """
        if schedule_type != "ifc_sched":
            return False
        
        month_length = config.get("month_length", 28)
        months_per_season = config.get("months_per_season", 4)
        special_month = config.get("special_month", 13)
        
        if not isinstance(month_length, int) or month_length < 1:
            return False
        
        if not isinstance(months_per_season, int) or months_per_season < 1:
            return False
        
        if not isinstance(special_month, int) or special_month < 1:
            return False
        
        # Validate that the calendar structure makes sense
        # 13 months * 28 days = 364 days + 1 New Year's Day = 365 days
        total_days = special_month * month_length
        if new_years_day := config.get("new_years_day", True):
            total_days += 1
        
        if total_days != 365:
            return False
        
        return True

    def calculate_seasons_for_range(
        self,
        schedule_type: str,
        start_date: datetime,
        end_date: datetime,
        config: dict[str, Any],
    ) -> list[tuple[datetime, datetime]]:
        """Calculate all seasons within a date range for International Fixed Calendar.
        
        This method generates all seasons that would have occurred between start_date
        and end_date based on the IFC schedule type's rules.
        
        Args:
            schedule_type: The schedule type identifier (should be "ifc_sched")
            start_date: The start of the date range (oldest score time)
            end_date: The end of the date range (current time)
            config: The schedule configuration from the database
            
        Returns:
            A list of (start_date, end_date) tuples for each season in the range,
            ordered from oldest to newest.
        """
        if schedule_type != "ifc_sched":
            return []
        
        tz_name = config.get("timezone", "UTC")
        tz = ZoneInfo(tz_name)
        
        start_date = start_date.astimezone(tz)
        end_date = end_date.astimezone(tz)
        
        month_length = config.get("month_length", 28)
        months_per_season = config.get("months_per_season", 4)
        new_years_day = config.get("new_years_day", True)
        
        seasons = []
        
        # Start from the beginning of the year containing start_date
        current_year = start_date.year
        
        while True:
            # Calculate epoch for this year (January 2)
            epoch = datetime(current_year, 1, 2, tzinfo=tz)
            
            # Calculate seasons for this year
            # There are 4 seasons: S1 (months 1-4), S2 (months 5-8), S3 (months 9-12), S4 (month 13)
            for season_num in range(4):
                season_start_month = season_num * months_per_season + 1
                
                # S4 is a special single-month season (month 13 only)
                if season_num == 3:  # S4 (0-indexed, so season_num 3)
                    season_end_month = season_start_month  # Only month 13
                else:
                    season_end_month = season_start_month + months_per_season - 1
                
                # Calculate days to season start
                days_to_start = (season_start_month - 1) * month_length
                if new_years_day and days_to_start >= 364:
                    days_to_start += 1
                
                # Calculate days to season end
                days_to_end = season_end_month * month_length
                if new_years_day and days_to_end >= 364:
                    days_to_end += 1
                
                season_start = epoch + timedelta(days=days_to_start)
                season_end = epoch + timedelta(days=days_to_end)
                
                # Only add if the season overlaps with our range
                if season_start < end_date and season_end > start_date:
                    seasons.append((season_start, season_end))
            
            # Handle New Year's Day if enabled
            if new_years_day:
                nye_start = datetime(current_year, 1, 1, tzinfo=tz)
                nye_end = datetime(current_year, 1, 2, tzinfo=tz)
                
                if nye_start < end_date and nye_end > start_date:
                    seasons.append((nye_start, nye_end))
            
            # Move to next year
            current_year += 1
            
            # Stop if we've passed the end date
            if datetime(current_year, 1, 1, tzinfo=tz) >= end_date:
                break
        
        return seasons
