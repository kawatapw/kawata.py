"""
Background Loops Module - Asynchronous Housekeeping Task Management

This module provides background housekeeping tasks for the osu! server application,
implementing asynchronous loops that perform periodic maintenance operations such
as removing expired privileges, disconnecting inactive players, and updating bot
status. These tasks run continuously in the background to maintain server health
and enforce business rules.

The module uses asyncio to create and manage background tasks that operate
independently of the main request handling loop. Each task is designed to be
resilient and self-contained, with appropriate error handling and logging to
ensure server stability.

Key Features:
    - Asynchronous background task management
    - Expired privilege removal and enforcement
    - Ghost player detection and disconnection
    - Bot status updates and maintenance
    - Debug level monitoring and adjustment
    - Configurable task intervals and thresholds
    - Comprehensive logging and error handling

Integration Points:
    - Player session management in app/state/sessions.py
    - Privilege system in app/constants/privileges.py
    - Packet handling in app/packets.py
    - Database operations in app/state/services.py
    - Logging system in app/logging.py
    - Settings configuration in app/settings.py

Housekeeping Tasks:
    - _remove_expired_donation_privileges: Remove expired donor privileges
    - _disconnect_ghosts: Disconnect inactive players
    - _update_bot_status: Update bot status and clear caches
    - DebugLevelWatcher.watch: Monitor and adjust debug levels

Task Intervals:
    - Expired privileges: Every 30 minutes
    - Ghost disconnection: Every 100 seconds (OSU_CLIENT_MIN_PING_INTERVAL / 3)
    - Bot status update: Every 5 minutes
    - Debug level watch: Every 1 second

Usage Pattern:
    # Initialize all housekeeping tasks
    await initialize_housekeeping_tasks()

    # Tasks run automatically in the background
    # No manual intervention required

    # Monitor task status through logging
    # Tasks log their activities for debugging

Related Files:
    - app/state/sessions.py: Session and player management
    - app/constants/privileges.py: Privilege definitions
    - app/packets.py: Packet creation utilities
    - app/logging.py: Logging utilities
    - app/settings.py: Server configuration
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import app.packets
import app.settings
import app.state
from app.constants.gamemodes import GameMode
from app.constants.privileges import Privileges
from app.logging import Ansi, log, logLevel
from app.repositories import seasons as seasons_repo
from app.repositories import stats as stats_repo
from app.schedule_types import get_provider_for_schedule_type
from app.utils import DebugLevelWatcher

OSU_CLIENT_MIN_PING_INTERVAL = 300000 // 1000  # defined by osu!


async def initialize_housekeeping_tasks() -> None:
    """Create tasks for each housekeeping tasks."""
    log("Initializing housekeeping tasks.", Ansi.LCYAN)

    loop = asyncio.get_running_loop()

    tasks = (
        _remove_expired_donation_privileges(interval=30 * 60),
        _update_bot_status(interval=5 * 60),
        _disconnect_ghosts(interval=OSU_CLIENT_MIN_PING_INTERVAL // 3),
        DebugLevelWatcher.watch(interval=1),
        check_season_schedules(interval=60),
        update_non_active_season_stats(interval=300),
    )

    log(f"Creating {len(tasks)} housekeeping tasks", Ansi.LCYAN)

    app.state.sessions.housekeeping_tasks.update(
        {loop.create_task(task) for task in tasks},
    )

    log(
        f"Successfully initialized {len(app.state.sessions.housekeeping_tasks)} housekeeping tasks",
        Ansi.LGREEN,
    )


async def _remove_expired_donation_privileges(interval: int) -> None:
    """Remove donation privileges from users with expired sessions."""
    while True:
        log(
            "Removing expired donation privileges.",
            Ansi.LMAGENTA,
            level=16,
            extra={
                "filter": {
                    "debugLevel": 1,
                },
            },
        )

        expired_donors: list[dict[str, Any]] | None = (
            await app.state.services.database.fetch_all(
                "SELECT id FROM users "
                "WHERE donor_end <= UNIX_TIMESTAMP() "
                "AND priv & :donor_priv",
                {"donor_priv": Privileges.DONATOR.value},
            )
        )

        if expired_donors is not None:
            for expired_donor in expired_donors:
                player = await app.state.sessions.players.from_cache_or_sql(
                    id=expired_donor["id"],
                )

                assert player is not None

                # TODO: perhaps make a `revoke_donor` method?
                await player.remove_privs(Privileges.DONATOR)
                player.donor_end = 0
                await app.state.services.database.execute(
                    "UPDATE users SET donor_end = 0 WHERE id = :id",
                    {"id": player.id},
                )

                if player.is_online:
                    player.enqueue(
                        app.packets.notification("Your supporter status has expired."),
                    )

                log(f"{player}'s supporter status has expired.", Ansi.LMAGENTA)

        await asyncio.sleep(interval)


async def _disconnect_ghosts(interval: int) -> None:
    """Actively disconnect users above the
    disconnection time threshold on the osu! server."""
    while True:
        await asyncio.sleep(interval)
        current_time = time.time()

        for player in app.state.sessions.players:
            if current_time - player.last_recv_time > OSU_CLIENT_MIN_PING_INTERVAL:
                log(f"Auto-dced {player}.", Ansi.LMAGENTA)
                player.logout()


async def _update_bot_status(interval: int) -> None:
    """Re roll the bot status, every `interval`."""
    while True:
        await asyncio.sleep(interval)
        app.packets.bot_stats.cache_clear()


async def check_season_schedules(interval: int = 60) -> None:
    """Check and auto-start/end seasons based on schedule configuration.

    This function also handles retroactive season creation on first run.
    When no seasons exist for a schedule, it will:
    1. Find the oldest score's play_time
    2. Create all seasons from that date to now for each schedule type
    3. Mark the current season as active
    4. Calculate stats for all created seasons

    Args:
        interval: Check interval in seconds (default: 60 seconds)
    """
    log("Starting season schedule checker", Ansi.LCYAN)

    while True:
        try:
            # Check if seasons are enabled via server_data
            seasons_enabled = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_enabled'",
            )

            if seasons_enabled != "1":
                log(
                    "Seasons not enabled, skipping check",
                    Ansi.LYELLOW,
                    level=logLevel.DEBUG,
                )
                await asyncio.sleep(interval)
                continue

            log("Checking season schedules...", Ansi.LCYAN, level=logLevel.DEBUG)

            # Get all schedules that need checking
            schedules: list[seasons_repo.SeasonSchedule] = (
                await seasons_repo.fetch_active_schedules()
            )

            if not schedules:
                log("No active schedules found", Ansi.LYELLOW, level=logLevel.DEBUG)
                await asyncio.sleep(interval)
                continue

            log(f"Found {len(schedules)} active schedule(s) to check", Ansi.LCYAN)

            for schedule in schedules:
                log(
                    f"Processing schedule: {schedule['name']} (ID: {schedule['id']}, Type: {schedule['schedule_type']})",
                    Ansi.LCYAN,
                    level=logLevel.DEBUG,
                )

                # Get the provider for this schedule type
                provider = get_provider_for_schedule_type(schedule["schedule_type"])
                if not provider:
                    log(
                        f"No provider found for schedule type: {schedule['schedule_type']}",
                        Ansi.LRED,
                        level=logLevel.ERROR,
                    )
                    continue

                log(
                    f"Using provider for schedule type: {schedule['schedule_type']}",
                    Ansi.LCYAN,
                    level=logLevel.DEBUG,
                )

                # Check if any seasons exist for this schedule
                existing_seasons = await seasons_repo.fetch_many_by_schedule(
                    schedule_id=schedule["id"],
                )

                log(
                    f"Found {len(existing_seasons)} existing season(s) for schedule '{schedule['name']}'",
                    Ansi.LCYAN,
                    level=logLevel.DEBUG,
                )

                if not existing_seasons:
                    # No seasons exist - do retroactive creation
                    log(
                        f"No seasons found for schedule '{schedule['name']}', performing retroactive creation",
                        Ansi.LCYAN,
                    )
                    await _retroactively_create_seasons(schedule, provider)
                    continue

                # Seasons exist - check if we need to create a new one or end an active one
                current_time = datetime.now(UTC)
                log(f"Current time: {current_time}", Ansi.LCYAN, level=logLevel.DEBUG)

                # Check if there's an active season for this schedule
                active_season = await seasons_repo.fetch_active_season_by_schedule(
                    schedule_id=schedule["id"],
                )

                if active_season is None:
                    log(
                        f"No active season found for schedule '{schedule['name']}'",
                        Ansi.LYELLOW,
                        level=logLevel.DEBUG,
                    )

                    # No active season - find the current season based on current time
                    current_season = None
                    for season in existing_seasons:
                        # Make database datetimes timezone-aware for comparison
                        start_date = season["start_date"]
                        end_date = season["end_date"]
                        if start_date.tzinfo is None:
                            start_date = start_date.replace(tzinfo=UTC)
                        if end_date.tzinfo is None:
                            end_date = end_date.replace(tzinfo=UTC)

                        log(
                            f"Checking season '{season['name']}': {start_date} to {end_date}",
                            Ansi.LCYAN,
                            level=logLevel.DEBUG,
                        )

                        if start_date <= current_time < end_date:
                            current_season = season
                            log(
                                f"Found current season: {season['name']}",
                                Ansi.LCYAN,
                                level=logLevel.DEBUG,
                            )
                            break

                    if current_season:
                        # Activate the current season
                        log(
                            f"Activating season: {current_season['name']} (ID: {current_season['id']})",
                            Ansi.LCYAN,
                        )
                        await seasons_repo.activate(current_season["id"])
                        log(
                            f"Successfully activated season: {current_season['name']}",
                            Ansi.LGREEN,
                        )
                    else:
                        log(
                            f"No season covers current time for schedule '{schedule['name']}', creating new season",
                            Ansi.LCYAN,
                        )

                        # No season covers current time - create a new one
                        start_date, end_date = provider.calculate_next_season(
                            schedule["schedule_type"],
                            current_time,
                            schedule["config"],
                        )

                        season_name = provider.get_season_name(
                            schedule["schedule_type"],
                            start_date,
                            schedule["config"],
                        )

                        log(
                            f"Creating new season: {season_name} ({start_date} to {end_date})",
                            Ansi.LCYAN,
                        )

                        new_season = await seasons_repo.create(
                            name=season_name,
                            schedule_id=schedule["id"],
                            start_date=start_date,
                            end_date=end_date,
                            is_active=True,
                            description=f"Auto-generated season for {schedule['name']}",
                        )

                        log(
                            f"Successfully created new season: {season_name} (ID: {new_season['id']})",
                            Ansi.LGREEN,
                        )

                else:
                    log(
                        f"Found active season: {active_season['name']} (ID: {active_season['id']})",
                        Ansi.LCYAN,
                        level=logLevel.DEBUG,
                    )

                    # Make database datetime timezone-aware for comparison
                    end_date = active_season["end_date"]
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=UTC)

                    log(
                        f"Active season ends at: {end_date}, current time: {current_time}",
                        Ansi.LCYAN,
                        level=logLevel.DEBUG,
                    )

                    if end_date <= current_time:
                        log(
                            f"Active season '{active_season['name']}' has ended, deactivating",
                            Ansi.LMAGENTA,
                        )

                        # Active season has ended - deactivate it and create next season
                        await seasons_repo.deactivate(active_season["id"])
                        log(
                            f"Successfully deactivated season: {active_season['name']}",
                            Ansi.LMAGENTA,
                        )

                        # Create next season
                        start_date, end_date = provider.calculate_next_season(
                            schedule["schedule_type"],
                            current_time,
                            schedule["config"],
                        )

                        season_name = provider.get_season_name(
                            schedule["schedule_type"],
                            start_date,
                            schedule["config"],
                        )

                        log(
                            f"Creating next season: {season_name} ({start_date} to {end_date})",
                            Ansi.LCYAN,
                        )

                        new_season = await seasons_repo.create(
                            name=season_name,
                            schedule_id=schedule["id"],
                            start_date=start_date,
                            end_date=end_date,
                            is_active=True,
                            description=f"Auto-generated season for {schedule['name']}",
                        )

                        log(
                            f"Successfully created next season: {season_name} (ID: {new_season['id']})",
                            Ansi.LGREEN,
                        )
                    else:
                        log(
                            f"Active season '{active_season['name']}' is still active",
                            Ansi.LCYAN,
                            level=logLevel.DEBUG,
                        )

        except Exception as e:
            log(f"Error in check_season_schedules: {e}", Ansi.LRED, exc_info=True)

        log(
            f"Season check complete, sleeping for {interval} seconds",
            Ansi.LCYAN,
            level=logLevel.DEBUG,
        )
        await asyncio.sleep(interval)


async def _retroactively_create_seasons(
    schedule: seasons_repo.SeasonSchedule,
    provider: Any,
) -> None:
    """Retroactively create seasons from the oldest score to now.

    Args:
        schedule: The schedule configuration
        provider: The schedule type provider
    """
    try:
        # Find the oldest score's play_time
        oldest_play_time = await app.state.services.database.fetch_val(
            "SELECT MIN(play_time) FROM scores",
        )

        if oldest_play_time is None:
            log(
                f"No scores found, cannot create seasons for schedule '{schedule['name']}'",
                Ansi.LYELLOW,
            )
            return

        # Convert to datetime if it's a string
        if isinstance(oldest_play_time, str):
            oldest_play_time = datetime.fromisoformat(oldest_play_time)

        # Ensure oldest_play_time is timezone-aware (UTC)
        if oldest_play_time.tzinfo is None:
            oldest_play_time = oldest_play_time.replace(tzinfo=UTC)

        current_time = datetime.now(UTC)

        log(
            f"Creating seasons from {oldest_play_time} to {current_time} for schedule '{schedule['name']}'",
            Ansi.LCYAN,
        )

        # Calculate all seasons from oldest score to now
        seasons_to_create = provider.calculate_seasons_for_range(
            schedule["schedule_type"],
            oldest_play_time,
            current_time,
            schedule["config"],
        )

        if not seasons_to_create:
            log(
                f"No seasons to create for schedule '{schedule['name']}'",
                Ansi.LYELLOW,
            )
            return

        # Create all seasons
        created_seasons = []
        for start_date, end_date in seasons_to_create:
            season_name = provider.get_season_name(
                schedule["schedule_type"],
                start_date,
                schedule["config"],
            )

            # Check if this season already exists
            existing = await seasons_repo.fetch_season_by_start_date(
                schedule_id=schedule["id"],
                start_date=start_date,
            )

            if existing:
                log(
                    f"Season '{season_name}' already exists, skipping",
                    Ansi.LYELLOW,
                )
                created_seasons.append(existing)
                continue

            # Determine if this is the current season
            is_active = start_date <= current_time < end_date

            new_season = await seasons_repo.create(
                name=season_name,
                schedule_id=schedule["id"],
                start_date=start_date,
                end_date=end_date,
                is_active=is_active,
                description=f"Retroactively created season for {schedule['name']}",
            )

            log(
                f"Created season: {season_name} (active: {is_active})",
                Ansi.LGREEN,
            )

            created_seasons.append(new_season)

        # Calculate stats for all created seasons
        log(
            f"Calculating stats for {len(created_seasons)} seasons",
            Ansi.LCYAN,
        )

        for season in created_seasons:
            await calculate_season_stats_for_all_users(season["id"])

        log(
            f"Retroactive season creation complete for schedule '{schedule['name']}'",
            Ansi.LGREEN,
        )

    except Exception as e:
        log(
            f"Error in retroactive season creation for schedule '{schedule['name']}': {e}",
            Ansi.LRED,
            level=logLevel.ERROR,
        )


async def update_non_active_season_stats(interval: int = 300) -> None:
    """Periodically update stats for non-active seasons.

    Args:
        interval: Update interval in seconds (default: 300 seconds / 5 minutes)
    """
    while True:
        try:
            seasons_enabled = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_enabled'",
            )

            if seasons_enabled != "1":
                await asyncio.sleep(interval)
                continue

            # Get all seasons that are currently active (within their date range)
            # but are NOT the active season type
            active_season_type_id = await app.state.services.database.fetch_val(
                "SELECT value FROM server_data WHERE type = 'seasons_active_type_id'",
            )

            current_time = datetime.now(UTC)
            non_active_seasons = await seasons_repo.fetch_non_active_seasons(
                active_season_type_id=(
                    int(active_season_type_id) if active_season_type_id else None
                ),
                current_time=current_time,
            )

            for season in non_active_seasons:
                # Skip seasons that have had their end calculation done
                if season["end_calculated"]:
                    continue

                # Update stats for this season with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        await seasons_repo.update_season_stats(season["id"])
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            log(
                                f"Failed to update stats for season {season['id']} after {max_retries} attempts: {e}",
                                Ansi.LRED,
                                level=logLevel.ERROR,
                            )
                        else:
                            await asyncio.sleep(2**attempt)  # Exponential backoff

        except Exception as e:
            log(
                f"Error in update_non_active_season_stats: {e}",
                Ansi.LRED,
                level=logLevel.ERROR,
            )

        await asyncio.sleep(interval)


async def calculate_season_stats_for_all_users(season_id: int) -> None:
    """Calculate stats for all users for a specific season.

    This is run in background when a new season is created.
    """
    try:
        # Get all users who have scores in this season's date range
        season = await seasons_repo.fetch_one(id=season_id)
        if not season:
            return

        users: list[dict[str, Any]] = (
            await app.state.services.database.fetch_all(
                "SELECT DISTINCT userid FROM scores "
                "WHERE play_time >= :start_date AND play_time < :end_date",
                {"start_date": season["start_date"], "end_date": season["end_date"]},
            )
            or []
        )

        user_ids = [user["userid"] for user in users]
        await stats_repo.ensure_season_rows_for_users(
            season_id=season_id,
            user_ids=user_ids,
        )

        for user in users:
            for mode in GameMode:
                try:
                    await seasons_repo.calculate_stats(
                        season_id=season_id,
                        user_id=user["userid"],
                        mode=mode.value,
                    )
                except Exception as e:
                    log(
                        f"Failed to calculate stats for user {user['userid']}: {e}",
                        Ansi.LRED,
                        level=logLevel.ERROR,
                    )

        log(f"Calculated stats for season {season_id}", Ansi.LGREEN)
    except Exception as e:
        log(f"Failed to calculate season stats: {e}", Ansi.LRED, level=logLevel.ERROR)
