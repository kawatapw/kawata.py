"""
Seasons Repository - Database Operations for Season Management

This module provides database operations for managing seasons in the osu! server
application. It implements the repository pattern for season data access, providing
a clean abstraction layer between the application logic and database operations
for season storage, retrieval, and management.

The repository handles all CRUD operations for seasons, including creation,
retrieval, updating, and management of season records. It supports multiple
schedule types and provides functions for managing season schedules, configurations,
and statistics.

Key Features:
    - Complete CRUD operations for seasons
    - Schedule type management
    - Season configuration management
    - Season statistics tracking
    - Active season management
    - Season transition support
    - Datetime-based season filtering

Integration Points:
    - Schedule type providers in app/schedule_types/
    - Player statistics in app/objects/player.py
    - Score submission in app/api/domains/osu.py
    - Background tasks in app/bg_loops.py
    - Database connection in app/state/services.py

Database Schema:
    - season_schedules: Schedule type configurations
    - seasons: Individual season records
    - season_config: Season-specific configuration
    - stats: Player statistics with season_id support

Usage Pattern:
    # Create a new season
    season = await create(
        name="Spring 2024",
        schedule_id=1,
        start_date=datetime(2024, 3, 20),
        end_date=datetime(2024, 6, 20)
    )
    
    # Fetch active season
    active = await fetch_active()
    
    # Fetch seasons containing a specific time
    seasons = await fetch_seasons_containing_time(datetime.now())
    
    # Update season stats
    await update_season_stats(season_id=1)

Related Files:
    - app/schedule_types/base.py: ScheduleTypeProvider ABC
    - app/repositories/stats.py: Stats repository
    - app/bg_loops.py: Background tasks
    - app/commands.py: Season management commands
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Boolean
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import JSON

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base
from app.logging import Ansi, log, error_catcher


class SeasonSchedulesTable(Base):
    __tablename__ = "season_schedules"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    name = Column("name", String(64), nullable=False)
    description = Column("description", String(256), nullable=True)
    schedule_type = Column("schedule_type", String(32), nullable=False)
    config = Column("config", JSON, nullable=False)
    is_default = Column("is_default", Boolean, nullable=False, server_default="0")
    created_at = Column("created_at", DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_season_schedules_name", name, unique=True),
    )


class SeasonsTable(Base):
    __tablename__ = "seasons"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    name = Column("name", String(64), nullable=False)
    schedule_id = Column("schedule_id", Integer, ForeignKey("season_schedules.id", ondelete="SET NULL"), nullable=True)
    start_date = Column("start_date", DateTime, nullable=False)
    end_date = Column("end_date", DateTime, nullable=False)
    is_active = Column("is_active", Boolean, nullable=False, server_default="0")
    end_calculated = Column("end_calculated", Boolean, nullable=False, server_default="0")
    awards_badges = Column("awards_badges", Boolean, nullable=False, server_default="0")
    description = Column("description", String(256), nullable=True)
    created_at = Column("created_at", DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_seasons_schedule_id", schedule_id),
        Index("idx_seasons_start_date", start_date),
        Index("idx_seasons_end_date", end_date),
        Index("idx_seasons_is_active", is_active),
    )


class SeasonConfigTable(Base):
    __tablename__ = "season_config"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    season_id = Column("season_id", Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    config_key = Column("config_key", String(64), nullable=False)
    config_value = Column("config_value", Text, nullable=True)

    __table_args__ = (
        Index("idx_season_config_season_key", season_id, config_key, unique=True),
    )


SEASON_READ_PARAMS = (
    SeasonsTable.id,
    SeasonsTable.name,
    SeasonsTable.schedule_id,
    SeasonsTable.start_date,
    SeasonsTable.end_date,
    SeasonsTable.is_active,
    SeasonsTable.end_calculated,
    SeasonsTable.awards_badges,
    SeasonsTable.description,
    SeasonsTable.created_at,
)

SCHEDULE_READ_PARAMS = (
    SeasonSchedulesTable.id,
    SeasonSchedulesTable.name,
    SeasonSchedulesTable.description,
    SeasonSchedulesTable.schedule_type,
    SeasonSchedulesTable.config,
    SeasonSchedulesTable.is_default,
    SeasonSchedulesTable.created_at,
)


class Season(TypedDict):
    id: int
    name: str
    schedule_id: int | None
    start_date: datetime
    end_date: datetime
    is_active: bool
    end_calculated: bool
    awards_badges: bool
    description: str | None
    created_at: datetime


class SeasonSchedule(TypedDict):
    id: int
    name: str
    description: str | None
    schedule_type: str
    config: dict[str, Any]
    is_default: bool
    created_at: datetime | None


class SeasonConfig(TypedDict):
    id: int
    season_id: int
    config_key: str
    config_value: str | None


@error_catcher
async def create(
    name: str,
    schedule_id: int | None,
    start_date: datetime,
    end_date: datetime,
    is_active: bool = False,
    awards_badges: bool = False,
    description: str | None = None,
) -> Season:
    """Create a new season in the database."""
    log(f"Creating season: {name} (schedule_id: {schedule_id}, active: {is_active})", Ansi.LCYAN)
    
    try:
        insert_stmt = insert(SeasonsTable).values(
            name=name,
            schedule_id=schedule_id,
            start_date=start_date,
            end_date=end_date,
            is_active=1 if is_active else 0,
            awards_badges=awards_badges,
            description=description,
        )
        rec_id = await app.state.services.database.execute(insert_stmt)
        log(f"Season insert executed, ID: {rec_id}", Ansi.LCYAN, level=logging.DEBUG)

        select_stmt = select(*SEASON_READ_PARAMS).where(SeasonsTable.id == rec_id)
        season = await app.state.services.database.fetch_one(select_stmt)
        
        if season is None:
            log(f"Failed to retrieve created season with ID: {rec_id}", Ansi.LRED, level=logging.ERROR)
            raise ValueError(f"Season with ID {rec_id} not found after creation")
        
        log(f"Season created successfully: {name} (ID: {rec_id})", Ansi.LGREEN)
        return cast(Season, season)
    except Exception as e:
        log(f"Error creating season '{name}': {e}", Ansi.LRED, level=logging.ERROR, exc_info=True)
        raise


@error_catcher
async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    is_active: bool | None = None,
) -> Season | None:
    """Fetch a single season from the database."""
    if id is None and name is None and is_active is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(*SEASON_READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(SeasonsTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(SeasonsTable.name == name)
    if is_active is not None:
        select_stmt = select_stmt.where(SeasonsTable.is_active == is_active)

    season = await app.state.services.database.fetch_one(select_stmt)
    return cast(Season | None, season)


@error_catcher
async def fetch_active() -> Season | None:
    """Fetch the currently active season."""
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.is_active == True)
    )
    season = await app.state.services.database.fetch_one(select_stmt)
    return cast(Season | None, season)


@error_catcher
async def fetch_active_season_by_schedule(schedule_id: int) -> Season | None:
    """Fetch the currently active season for a specific schedule."""
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.schedule_id == schedule_id)
        .where(SeasonsTable.is_active == True)
    )
    season = await app.state.services.database.fetch_one(select_stmt)
    return cast(Season | None, season)


async def fetch_season_by_start_date(schedule_id: int, start_date: datetime) -> Season | None:
    """Fetch a season by schedule_id and start_date (to prevent duplicates)."""
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.schedule_id == schedule_id)
        .where(SeasonsTable.start_date == start_date)
    )
    season = await app.state.services.database.fetch_one(select_stmt)
    return cast(Season | None, season)


@error_catcher
@error_catcher
async def fetch_schedule_by_id(schedule_id: int) -> SeasonSchedule | None:
    """Fetch a schedule by its ID."""
    select_stmt = (
        select(*SCHEDULE_READ_PARAMS)
        .where(SeasonSchedulesTable.id == schedule_id)
    )
    schedule = await app.state.services.database.fetch_one(select_stmt)
    if schedule is None:
        return None
    
    # Parse JSON config if it's a string
    if isinstance(schedule.get("config"), str):
        schedule["config"] = json.loads(schedule["config"])
    
    return cast(SeasonSchedule, schedule)


@error_catcher
async def fetch_many_schedules() -> list[SeasonSchedule]:
    """Fetch all schedules."""
    select_stmt = select(*SCHEDULE_READ_PARAMS)
    schedules: list[dict[str, Any]] = await app.state.services.database.fetch_all(select_stmt) or []

    # Parse JSON config for each schedule if it's a string
    for schedule in schedules:
        if isinstance(schedule.get("config"), str):
            schedule["config"] = json.loads(schedule["config"])

    return cast(list[SeasonSchedule], schedules)


@error_catcher
async def fetch_default_schedule() -> SeasonSchedule | None:
    """Fetch the default/active schedule (is_default = True)."""
    select_stmt = (
        select(*SCHEDULE_READ_PARAMS)
        .where(SeasonSchedulesTable.is_default == True)
    )
    schedule = await app.state.services.database.fetch_one(select_stmt)
    if schedule is None:
        return None
    
    # Parse JSON config if it's a string
    if isinstance(schedule.get("config"), str):
        schedule["config"] = json.loads(schedule["config"])
    
    return cast(SeasonSchedule, schedule)


@error_catcher
async def fetch_active_season_by_type() -> Season | None:
    """Fetch the active season for the configured active season type."""
    active_type_id = await app.state.services.database.fetch_val(
        "SELECT value FROM server_data WHERE type = 'seasons_active_type_id'"
    )
    
    if not active_type_id:
        return None
    
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.schedule_id == int(active_type_id))
        .where(SeasonsTable.is_active == True)
    )
    season = await app.state.services.database.fetch_one(select_stmt)
    return cast(Season | None, season)


@error_catcher
async def fetch_non_active_seasons(
    active_season_type_id: int | None,
    current_time: datetime,
) -> list[Season]:
    """Fetch all seasons that are currently active but not the active season type."""
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.start_date <= current_time)
        .where(SeasonsTable.end_date > current_time)
        .where(SeasonsTable.is_active == True)
    )
    
    if active_season_type_id is not None:
        select_stmt = select_stmt.where(SeasonsTable.schedule_id != active_season_type_id)
    
    seasons = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Season], seasons)


@error_catcher
async def fetch_count() -> int:
    """Fetch the total number of seasons in the database."""
    select_stmt = select(func.count().label("count")).select_from(SeasonsTable)
    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


@error_catcher
async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Season]:
    """Fetch multiple seasons from the database."""
    select_stmt = select(*SEASON_READ_PARAMS).order_by(SeasonsTable.start_date.desc())
    
    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    seasons = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Season], seasons)


@error_catcher
async def partial_update(
    id: int,
    name: str | _UnsetSentinel = UNSET,
    schedule_id: int | None | _UnsetSentinel = UNSET,
    start_date: datetime | _UnsetSentinel = UNSET,
    end_date: datetime | _UnsetSentinel = UNSET,
    is_active: bool | _UnsetSentinel = UNSET,
    end_calculated: bool | _UnsetSentinel = UNSET,
    awards_badges: bool | _UnsetSentinel = UNSET,
    description: str | None | _UnsetSentinel = UNSET,
) -> Season | None:
    """Update a season in the database."""
    update_stmt = update(SeasonsTable).where(SeasonsTable.id == id)
    
    if not isinstance(name, _UnsetSentinel):
        update_stmt = update_stmt.values(name=name)
    if not isinstance(schedule_id, _UnsetSentinel):
        update_stmt = update_stmt.values(schedule_id=schedule_id)
    if not isinstance(start_date, _UnsetSentinel):
        update_stmt = update_stmt.values(start_date=start_date)
    if not isinstance(end_date, _UnsetSentinel):
        update_stmt = update_stmt.values(end_date=end_date)
    if not isinstance(is_active, _UnsetSentinel):
        update_stmt = update_stmt.values(is_active=is_active)
    if not isinstance(end_calculated, _UnsetSentinel):
        update_stmt = update_stmt.values(end_calculated=end_calculated)
    if not isinstance(awards_badges, _UnsetSentinel):
        update_stmt = update_stmt.values(awards_badges=awards_badges)
    if not isinstance(description, _UnsetSentinel):
        update_stmt = update_stmt.values(description=description)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*SEASON_READ_PARAMS).where(SeasonsTable.id == id)
    season = await app.state.services.database.fetch_one(select_stmt)
    return cast(Season | None, season)


@error_catcher
async def activate(id: int) -> Season | None:
    """Activate a season (set is_active to True)."""
    log(f"Activating season ID: {id}", Ansi.LCYAN, level=logging.DEBUG)
    return await partial_update(id, is_active=True)


@error_catcher
async def deactivate(id: int) -> Season | None:
    """Deactivate a season (set is_active to False)."""
    log(f"Deactivating season ID: {id}", Ansi.LCYAN, level=logging.DEBUG)
    return await partial_update(id, is_active=False)


@error_catcher
@error_catcher
async def fetch_active_schedules() -> list[SeasonSchedule]:
    """Fetch all schedules that need checking for season transitions."""
    select_stmt = select(*SCHEDULE_READ_PARAMS)
    schedules: list[dict[str, Any]] = await app.state.services.database.fetch_all(select_stmt) or []
    
    # Parse JSON config for each schedule if it's a string
    for schedule in schedules:
        if isinstance(schedule.get("config"), str):
            schedule["config"] = json.loads(schedule["config"])
    
    return cast(list[SeasonSchedule], schedules)


@error_catcher
async def create_schedule(
    name: str,
    schedule_type: str,
    config: dict[str, Any],
    description: str | None = None,
    is_default: bool = False,
) -> SeasonSchedule:
    """Create a new season schedule with validation."""
    log(f"Creating schedule: {name} (type: {schedule_type})", Ansi.LCYAN, level=logging.DEBUG)
    insert_stmt = insert(SeasonSchedulesTable).values(
        name=name,
        description=description,
        schedule_type=schedule_type,
        config=json.dumps(config),
        is_default=is_default,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*SCHEDULE_READ_PARAMS).where(SeasonSchedulesTable.id == rec_id)
    schedule = await app.state.services.database.fetch_one(select_stmt)
    assert schedule is not None
    log(f"Schedule created successfully: {name} (ID: {rec_id})", Ansi.LGREEN, level=logging.DEBUG)
    return cast(SeasonSchedule, schedule)


@error_catcher
async def fetch_seasons_containing_time(play_time: datetime) -> list[Season]:
    """Fetch all seasons that contain the given play_time."""
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.start_date <= play_time)
        .where(SeasonsTable.end_date > play_time)
    )
    seasons = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Season], seasons)


@error_catcher
async def update_season_stats(season_id: int) -> None:
    """Update stats for a season (used for periodic updates of non-active seasons).
    
    This reuses the same per-user seasonal calculation logic as tools/recalc.py
    to keep seasonal stats 1:1 with non-seasonal stats (weighted pp/acc).
    """
    log(f"Updating stats for season ID: {season_id}", Ansi.LCYAN, level=logging.DEBUG)

    season = await fetch_one(id=season_id)
    if not season:
        log(
            f"Season ID {season_id} not found, skipping stats update",
            Ansi.LYELLOW,
            level=logging.WARNING,
        )
        return

    rows: list[dict[str, Any]] = await app.state.services.database.fetch_all(
        """
        SELECT DISTINCT s.userid AS user_id, s.mode
        FROM scores s
        WHERE s.play_time >= :start_date AND s.play_time < :end_date
        """,
        {
            "start_date": season["start_date"],
            "end_date": season["end_date"],
        },
    ) or []

    for row in rows:
        try:
            await calculate_stats(
                season_id=season_id,
                user_id=row["user_id"],
                mode=row["mode"],
            )
        except Exception as e:
            log(
                f"Error updating stats for season {season_id} "
                f"user {row['user_id']} mode {row['mode']}: {e}",
                Ansi.LRED,
                level=logging.ERROR,
            )

    log(
        f"Stats updated successfully for season ID: {season_id}",
        Ansi.LGREEN,
        level=logging.DEBUG,
    )


@error_catcher
async def calculate_stats(season_id: int, user_id: int, mode: int) -> None:
    """Calculate stats for a user in a season by aggregating scores.
    
    This function aggregates scores within the season's date range and updates
    the stats table with season_id. Uses weighted pp/accuracy calculation
    matching the logic in tools/recalc.py.
    """
    # Get season info
    season = await fetch_one(id=season_id)
    if not season:
        log(f"Season ID {season_id} not found, skipping stats calculation", Ansi.LYELLOW, level=logging.WARNING)
        return
    
    # First check if there are any scores for this user/mode in the season date range
    # This prevents the "Column 'mode' cannot be null" error when no scores exist
    check_query = """
        SELECT COUNT(*) as score_count
        FROM scores s
        WHERE s.userid = :user_id AND s.mode = :mode
        AND s.play_time >= :start_date AND s.play_time < :end_date
    """
    
    check_result = await app.state.services.database.fetch_one(
        check_query,
        {
            "user_id": user_id,
            "mode": mode,
            "start_date": season["start_date"],
            "end_date": season["end_date"],
        },
    )
    
    if not check_result or check_result["score_count"] == 0:
        # No scores for this user/mode in the season date range, skip
        return
    
    # Get best scores for weighted pp/accuracy calculation (ranked/approved maps only)
    best_scores = await app.state.services.database.fetch_all(
        """
        SELECT s.pp, s.acc FROM scores s
        INNER JOIN maps m ON s.map_md5 = m.md5
        WHERE s.userid = :user_id AND s.mode = :mode
        AND s.status = 2 AND m.status IN (2, 3)
        AND s.play_time >= :start_date AND s.play_time < :end_date
        ORDER BY s.pp DESC
        """,
        {
            "user_id": user_id,
            "mode": mode,
            "start_date": season["start_date"],
            "end_date": season["end_date"],
        },
    )
    
    total_scores = len(best_scores) if best_scores else 0
    
    # Calculate weighted accuracy
    if total_scores > 0 and best_scores:
        weighted_acc = sum(row["acc"] * 0.95**i for i, row in enumerate(best_scores))
        bonus_acc = 100.0 / (20 * (1 - 0.95**total_scores))
        acc = (weighted_acc * bonus_acc) / 100
        
        # Calculate weighted pp
        weighted_pp = sum(row["pp"] * 0.95**i for i, row in enumerate(best_scores))
        bonus_pp = 416.6667 * (1 - 0.9994**total_scores)
        pp = round(weighted_pp + bonus_pp)
    else:
        acc = 0.0
        pp = 0
    
    # Aggregate other stats (tscore, rscore, plays, playtime, etc.)
    #
    # NOTE: the `stats` table uses different column types:
    # - tscore, rscore: bigint unsigned - can hold up to 18,446,744,073,709,551,615
    # - pp, plays, playtime, max_combo, total_hits, xh_count, x_count, sh_count, s_count, a_count: int unsigned - can hold up to 4,294,967,295
    # Clamp to the appropriate limits to guarantee inserts succeed.
    bigint_max = 18_446_744_073_709_551_615
    int32_max = 4_294_967_295
    stats_query = """
        INSERT INTO stats (id, mode, season_id, tscore, rscore, pp, plays, playtime,
                          acc, max_combo, total_hits, replay_views, xh_count, x_count,
                          sh_count, s_count, a_count)
        SELECT
            s.userid as id,
            s.mode,
            :season_id as season_id,
            LEAST(COALESCE(SUM(s.score), 0), :bigint_max) as tscore,
            LEAST(COALESCE(SUM(CASE WHEN s.status = 2 THEN s.score ELSE 0 END), 0), :bigint_max) as rscore,
            :pp as pp,
            LEAST(COUNT(*), :int32_max) as plays,
            LEAST(COALESCE(SUM(s.time_elapsed), 0), :int32_max) as playtime,
            :acc as acc,
            LEAST(COALESCE(MAX(s.max_combo), 0), :int32_max) as max_combo,
            LEAST(COALESCE(SUM(s.n300 + s.n100 + s.n50), 0), :int32_max) as total_hits,
            0 as replay_views,
            LEAST(COALESCE(SUM(CASE WHEN s.grade = 'XH' THEN 1 ELSE 0 END), 0), :int32_max) as xh_count,
            LEAST(COALESCE(SUM(CASE WHEN s.grade = 'X' THEN 1 ELSE 0 END), 0), :int32_max) as x_count,
            LEAST(COALESCE(SUM(CASE WHEN s.grade = 'SH' THEN 1 ELSE 0 END), 0), :int32_max) as sh_count,
            LEAST(COALESCE(SUM(CASE WHEN s.grade = 'S' THEN 1 ELSE 0 END), 0), :int32_max) as s_count,
            LEAST(COALESCE(SUM(CASE WHEN s.grade = 'A' THEN 1 ELSE 0 END), 0), :int32_max) as a_count
        FROM scores s
        WHERE s.userid = :user_id AND s.mode = :mode
        AND s.play_time >= :start_date AND s.play_time < :end_date
        ON DUPLICATE KEY UPDATE
            tscore = IF(VALUES(season_id) = season_id, VALUES(tscore), tscore),
            rscore = IF(VALUES(season_id) = season_id, VALUES(rscore), rscore),
            pp = IF(VALUES(season_id) = season_id, VALUES(pp), pp),
            plays = IF(VALUES(season_id) = season_id, VALUES(plays), plays),
            playtime = IF(VALUES(season_id) = season_id, VALUES(playtime), playtime),
            acc = IF(VALUES(season_id) = season_id, VALUES(acc), acc),
            max_combo = IF(VALUES(season_id) = season_id, VALUES(max_combo), max_combo),
            total_hits = IF(VALUES(season_id) = season_id, VALUES(total_hits), total_hits),
            xh_count = IF(VALUES(season_id) = season_id, VALUES(xh_count), xh_count),
            x_count = IF(VALUES(season_id) = season_id, VALUES(x_count), x_count),
            sh_count = IF(VALUES(season_id) = season_id, VALUES(sh_count), sh_count),
            s_count = IF(VALUES(season_id) = season_id, VALUES(s_count), s_count),
            a_count = IF(VALUES(season_id) = season_id, VALUES(a_count), a_count)
    """
    
    try:
        await app.state.services.database.execute(
            stats_query,
            {
                "season_id": season_id,
                "user_id": user_id,
                "mode": mode,
                "pp": pp,
                "acc": acc,
                "bigint_max": bigint_max,
                "int32_max": int32_max,
                "start_date": season["start_date"],
                "end_date": season["end_date"],
            },
        )
        
        # Verify the stats were created/updated
        verify_query = """
            SELECT COUNT(*) as stats_count
            FROM stats
            WHERE id = :user_id AND mode = :mode AND season_id = :season_id
        """
        
        verify_result = await app.state.services.database.fetch_one(
            verify_query,
            {
                "user_id": user_id,
                "mode": mode,
                "season_id": season_id,
            },
        )
        
        if verify_result and verify_result["stats_count"] > 0:
            log(f"Successfully calculated stats for user {user_id} mode {mode} season {season_id}",
                Ansi.LGREEN, level=logging.DEBUG)
            
            # Update Redis leaderboard for this season
            await update_season_leaderboard(season_id, user_id, mode, pp)
            
    except Exception as e:
        log(f"Error calculating stats for user {user_id} mode {mode} season {season_id}: {e}",
            Ansi.LRED, level=logging.ERROR)
        raise


@error_catcher
async def update_season_leaderboard(season_id: int, user_id: int, mode: int, pp: int) -> None:
    """Update the Redis leaderboard for a specific season.
    
    Args:
        season_id: The ID of the season.
        user_id: The ID of the user.
        mode: The game mode.
        pp: The performance points to set on the leaderboard.
    """
    try:
        await app.state.services.redis.zadd(
            f"bancho:leaderboard:{mode}:season:{season_id}",
            {str(user_id): pp},
        )
    except Exception as e:
        log(f"Error updating season leaderboard for user {user_id} mode {mode} season {season_id}: {e}",
            Ansi.LRED, level=logging.ERROR)


@error_catcher
async def fetch_many_by_schedule(schedule_id: int) -> list[Season]:
    """Fetch all seasons for a specific schedule.
    
    Args:
        schedule_id: The ID of the schedule to fetch seasons for.
        
    Returns:
        A list of Season objects for the given schedule.
    """
    select_stmt = (
        select(*SEASON_READ_PARAMS)
        .where(SeasonsTable.schedule_id == schedule_id)
        .order_by(SeasonsTable.start_date.asc())
    )
    seasons = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Season], seasons)
