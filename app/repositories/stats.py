"""
Stats Repository - Database Operations for Player Statistics Management

This module provides database operations for managing player statistics in the
osu! server application. It implements the repository pattern for statistics
data access, providing a clean abstraction layer between the application logic
and database operations for statistics storage, retrieval, and management.

The repository handles all CRUD operations for player statistics, including
creation, retrieval, updating, and management of statistics records across
all osu! game modes. It tracks comprehensive gameplay metrics including
scores, performance points, accuracy, play counts, and grade distributions.

Key Features:
    - Complete CRUD operations for player statistics
    - Support for all osu! game modes (vanilla, relax, autopilot)
    - Comprehensive statistics tracking (scores, PP, accuracy, etc.)
    - Grade distribution tracking (XH, X, SH, S, A counts)
    - Replay view counting for popularity metrics
    - Batch operations for multi-mode statistics
    - Type-safe data access with TypedDict definitions
    - Integration with player and score management systems

Integration Points:
    - Player statistics in app/objects/player.py
    - Score submission in app/api/domains/osu.py
    - Leaderboard generation in app/api/v2/players.py
    - Performance calculation in app/usecases/performance.py
    - Database connection in app/state/services.py

Database Schema:
    - id: Player ID (foreign key to users table)
    - mode: Game mode (0-8 for different mode combinations)
    - tscore: Total score across all plays
    - rscore: Ranked score (best scores on ranked maps)
    - pp: Performance points
    - plays: Total number of plays
    - playtime: Total playtime in seconds
    - acc: Average accuracy percentage
    - max_combo: Maximum combo achieved
    - total_hits: Total number of hits across all plays
    - replay_views: Number of times replays were viewed
    - xh_count: Number of XH (SS with Hidden) grades
    - x_count: Number of X (SS) grades
    - sh_count: Number of SH (S with Hidden) grades
    - s_count: Number of S grades
    - a_count: Number of A grades

Statistics Structure:
    - id: Player identifier
    - mode: Game mode identifier
    - tscore: Total score
    - rscore: Ranked score
    - pp: Performance points
    - plays: Play count
    - playtime: Total playtime
    - acc: Average accuracy
    - max_combo: Maximum combo
    - total_hits: Total hits
    - replay_views: Replay view count
    - xh_count, x_count, sh_count, s_count, a_count: Grade counts

Game Modes:
    - 0: Vanilla osu!standard
    - 1: Vanilla osu!taiko
    - 2: Vanilla osu!catch
    - 3: Vanilla osu!mania
    - 4: Relax osu!standard
    - 5: Relax osu!taiko
    - 6: Relax osu!catch
    - 8: Autopilot osu!standard

Usage Pattern:
    # Create statistics for a specific mode
    stat = await create(player_id=12345, mode=0)
    
    # Create statistics for all modes
    stats = await create_all_modes(player_id=12345)
    
    # Fetch statistics for a player and mode
    stat = await fetch_one(player_id=12345, mode=0)
    
    # Fetch statistics with filtering
    stats = await fetch_many(
        player_id=12345,
        mode=0,
        page=1,
        page_size=10
    )
    
    # Update statistics
    updated = await partial_update(
        player_id=12345,
        mode=0,
        pp=1000,
        plays=500,
        acc=95.5
    )

Related Files:
    - app/objects/player.py: Player class with statistics
    - app/api/domains/osu.py: Score submission with stat updates
    - app/api/v2/players.py: Player profile with statistics display
    - app/usecases/performance.py: Performance calculation
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base


class StatsTable(Base):
    __tablename__ = "stats"

    id = Column("id", Integer, nullable=False, primary_key=True)
    mode = Column("mode", TINYINT(1), primary_key=True)
    season_id = Column("season_id", INTEGER(unsigned=True), nullable=False, default=0, primary_key=True)
    tscore = Column("tscore", BigInteger, nullable=False, server_default="0")
    rscore = Column("rscore", BigInteger, nullable=False, server_default="0")
    pp = Column("pp", Integer, nullable=False, server_default="0")
    plays = Column("plays", Integer, nullable=False, server_default="0")
    playtime = Column("playtime", Integer, nullable=False, server_default="0")
    acc = Column(
        "acc",
        FLOAT(precision=6, scale=3),
        nullable=False,
        server_default="0.000",
    )
    max_combo = Column("max_combo", Integer, nullable=False, server_default="0")
    total_hits = Column("total_hits", Integer, nullable=False, server_default="0")
    replay_views = Column("replay_views", Integer, nullable=False, server_default="0")
    xh_count = Column("xh_count", Integer, nullable=False, server_default="0")
    x_count = Column("x_count", Integer, nullable=False, server_default="0")
    sh_count = Column("sh_count", Integer, nullable=False, server_default="0")
    s_count = Column("s_count", Integer, nullable=False, server_default="0")
    a_count = Column("a_count", Integer, nullable=False, server_default="0")

    __table_args__ = (
        Index("stats_mode_index", mode),
        Index("stats_pp_index", pp),
        Index("stats_tscore_index", tscore),
        Index("stats_rscore_index", rscore),
        Index("idx_season_id", season_id),
    )


READ_PARAMS = (
    StatsTable.id,
    StatsTable.mode,
    StatsTable.season_id,
    StatsTable.tscore,
    StatsTable.rscore,
    StatsTable.pp,
    StatsTable.plays,
    StatsTable.playtime,
    StatsTable.acc,
    StatsTable.max_combo,
    StatsTable.total_hits,
    StatsTable.replay_views,
    StatsTable.xh_count,
    StatsTable.x_count,
    StatsTable.sh_count,
    StatsTable.s_count,
    StatsTable.a_count,
)


class Stat(TypedDict):
    id: int
    mode: int
    season_id: int | None
    tscore: int
    rscore: int
    pp: int
    plays: int
    playtime: int
    acc: float
    max_combo: int
    total_hits: int
    replay_views: int
    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int


async def create(player_id: int, mode: int, season_id: int = 0) -> Stat:
    """Create a new player stats entry in the database."""
    insert_stmt = insert(StatsTable).values(id=player_id, mode=mode, season_id=season_id)
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(StatsTable.id == rec_id)
    stat = await app.state.services.database.fetch_one(select_stmt)
    assert stat is not None
    return cast(Stat, stat)


async def create_all_modes(player_id: int) -> list[Stat]:
    """Create new player stats entries for each game mode in the database."""
    insert_stmt = insert(StatsTable).values(
        [
            {"id": player_id, "mode": mode}
            for mode in (
                0,  # vn!std
                1,  # vn!taiko
                2,  # vn!catch
                3,  # vn!mania
                4,  # rx!std
                5,  # rx!taiko
                6,  # rx!catch
                8,  # ap!std
            )
        ],
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(StatsTable.id == player_id)
    stats = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Stat], stats)


SEASONAL_MODES: tuple[int, ...] = (
    0,  # vn!std
    1,  # vn!taiko
    2,  # vn!catch
    3,  # vn!mania
    4,  # rx!std
    5,  # rx!taiko
    6,  # rx!catch
    8,  # ap!std
)


async def create_all_modes_for_season(player_id: int, season_id: int) -> list[Stat]:
    """Ensure stats rows exist for all modes for a specific season.

    Safe to call repeatedly; duplicates are ignored/no-op due to unique key.
    """
    values = [
        {"id": player_id, "mode": mode, "season_id": season_id} for mode in SEASONAL_MODES
    ]
    insert_stmt = mysql_insert(StatsTable).values(values)
    insert_stmt = insert_stmt.on_duplicate_key_update(id=insert_stmt.inserted.id)
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.season_id == season_id)
    )
    stats = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Stat], stats)


async def ensure_season_rows_for_users(season_id: int, user_ids: list[int]) -> None:
    """Bulk ensure seasonal stats rows exist for many users.

    This creates all 8 mode rows for each user_id and is safe to call repeatedly.
    """
    if not user_ids:
        return

    values = [
        {"id": user_id, "mode": mode, "season_id": season_id}
        for user_id in user_ids
        for mode in SEASONAL_MODES
    ]
    insert_stmt = mysql_insert(StatsTable).values(values)
    insert_stmt = insert_stmt.on_duplicate_key_update(id=insert_stmt.inserted.id)
    await app.state.services.database.execute(insert_stmt)


async def fetch_one(player_id: int, mode: int, season_id: int | None = None) -> Stat | None:
    """Fetch a player stats entry from the database."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    if season_id is not None:
        select_stmt = select_stmt.where(StatsTable.season_id == season_id)
    else:
        select_stmt = select_stmt.where(StatsTable.season_id == 0)
    stat = await app.state.services.database.fetch_one(select_stmt)
    return cast(Stat | None, stat)


async def fetch_count(
    player_id: int | None = None,
    mode: int | None = None,
    season_id: int | None = None,
) -> int:
    select_stmt = select(func.count().label("count")).select_from(StatsTable)
    if player_id is not None:
        select_stmt = select_stmt.where(StatsTable.id == player_id)
    if mode is not None:
        select_stmt = select_stmt.where(StatsTable.mode == mode)
    if season_id is not None:
        select_stmt = select_stmt.where(StatsTable.season_id == season_id)
    else:
        select_stmt = select_stmt.where(StatsTable.season_id == 0)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    player_id: int | None = None,
    mode: int | None = None,
    season_id: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Stat]:
    select_stmt = select(*READ_PARAMS)
    if player_id is not None:
        select_stmt = select_stmt.where(StatsTable.id == player_id)
    if mode is not None:
        select_stmt = select_stmt.where(StatsTable.mode == mode)
    if season_id is not None:
        select_stmt = select_stmt.where(StatsTable.season_id == season_id)
    else:
        select_stmt = select_stmt.where(StatsTable.season_id == 0)
    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    stats = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Stat], stats)


async def partial_update(
    player_id: int,
    mode: int,
    season_id: int | None = None,
    tscore: int | _UnsetSentinel = UNSET,
    rscore: int | _UnsetSentinel = UNSET,
    pp: int | _UnsetSentinel = UNSET,
    plays: int | _UnsetSentinel = UNSET,
    playtime: int | _UnsetSentinel = UNSET,
    acc: float | _UnsetSentinel = UNSET,
    max_combo: int | _UnsetSentinel = UNSET,
    total_hits: int | _UnsetSentinel = UNSET,
    replay_views: int | _UnsetSentinel = UNSET,
    xh_count: int | _UnsetSentinel = UNSET,
    x_count: int | _UnsetSentinel = UNSET,
    sh_count: int | _UnsetSentinel = UNSET,
    s_count: int | _UnsetSentinel = UNSET,
    a_count: int | _UnsetSentinel = UNSET,
) -> Stat | None:
    """Update a player stats entry in the database."""
    update_stmt = (
        update(StatsTable)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    if season_id is not None:
        update_stmt = update_stmt.where(StatsTable.season_id == season_id)
    else:
        update_stmt = update_stmt.where(StatsTable.season_id == 0)
    if not isinstance(tscore, _UnsetSentinel):
        update_stmt = update_stmt.values(tscore=tscore)
    if not isinstance(rscore, _UnsetSentinel):
        update_stmt = update_stmt.values(rscore=rscore)
    if not isinstance(pp, _UnsetSentinel):
        update_stmt = update_stmt.values(pp=pp)
    if not isinstance(plays, _UnsetSentinel):
        update_stmt = update_stmt.values(plays=plays)
    if not isinstance(playtime, _UnsetSentinel):
        update_stmt = update_stmt.values(playtime=playtime)
    if not isinstance(acc, _UnsetSentinel):
        update_stmt = update_stmt.values(acc=acc)
    if not isinstance(max_combo, _UnsetSentinel):
        update_stmt = update_stmt.values(max_combo=max_combo)
    if not isinstance(total_hits, _UnsetSentinel):
        update_stmt = update_stmt.values(total_hits=total_hits)
    if not isinstance(replay_views, _UnsetSentinel):
        update_stmt = update_stmt.values(replay_views=replay_views)
    if not isinstance(xh_count, _UnsetSentinel):
        update_stmt = update_stmt.values(xh_count=xh_count)
    if not isinstance(x_count, _UnsetSentinel):
        update_stmt = update_stmt.values(x_count=x_count)
    if not isinstance(sh_count, _UnsetSentinel):
        update_stmt = update_stmt.values(sh_count=sh_count)
    if not isinstance(s_count, _UnsetSentinel):
        update_stmt = update_stmt.values(s_count=s_count)
    if not isinstance(a_count, _UnsetSentinel):
        update_stmt = update_stmt.values(a_count=a_count)

    await app.state.services.database.execute(update_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(StatsTable.id == player_id)
        .where(StatsTable.mode == mode)
    )
    if season_id is not None:
        select_stmt = select_stmt.where(StatsTable.season_id == season_id)
    else:
        select_stmt = select_stmt.where(StatsTable.season_id == 0)
    stat = await app.state.services.database.fetch_one(select_stmt)
    return cast(Stat | None, stat)

