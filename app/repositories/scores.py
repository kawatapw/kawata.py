"""
Scores Repository - Database Operations for Score Management

This module provides database operations for managing gameplay scores in the
osu! server application. It implements the repository pattern for score data
access, providing a clean abstraction layer between the application logic and
database operations for score storage, retrieval, and management.

The repository handles all CRUD operations for scores, including creation,
retrieval, updating, and management of score records. It supports comprehensive
score data including performance metrics, hit counts, mods, and anti-cheat
information for all osu! game modes.

Key Features:
    - Complete CRUD operations for score data
    - Comprehensive score metadata storage
    - Performance point (PP) and accuracy tracking
    - Anti-cheat flag and checksum management
    - Score status management (failed, submitted, best)
    - Integration with beatmap and player systems
    - Cheat value tracking and analysis
    - Pinned score support for highlighting

Integration Points:
    - Score submission in app/api/domains/osu.py
    - Leaderboard generation in app/api/v2/players.py
    - Performance calculation in app/usecases/performance.py
    - Beatmap management in app/objects/beatmap.py
    - Player statistics in app/objects/player.py
    - Database connection in app/state/services.py

Database Schema:
    - id: Primary key with auto-increment
    - map_md5: Beatmap MD5 hash (foreign key to maps table)
    - score: Total score value
    - pp: Performance points earned
    - acc: Accuracy percentage
    - max_combo: Maximum combo achieved
    - mods: Bitwise mods applied
    - n300, n100, n50, nmiss, ngeki, nkatu: Hit counts
    - grade: Letter grade (N, F, D, C, B, A, S, SH, X, XH)
    - status: Submission status (failed, submitted, best)
    - mode: Game mode (osu!, taiko, catch, mania)
    - play_time: When the score was played
    - time_elapsed: Time taken to complete the map
    - client_flags: Anti-cheat flags from client
    - userid: Player who set the score
    - perfect: Whether the score is a full combo
    - online_checksum: Anti-cheat checksum

Score Structure:
    - id: Unique identifier for the score
    - map_md5: Beatmap that was played
    - score: Total score value
    - pp: Performance points earned
    - acc: Accuracy percentage
    - max_combo: Maximum combo achieved
    - mods: Bitwise mods applied
    - mods_readable: Human-readable mod string
    - n300, n100, n50, nmiss, ngeki, nkatu: Hit counts
    - grade: Letter grade
    - status: Submission status
    - mode: Game mode
    - play_time: When the score was played
    - time_elapsed: Time taken to complete
    - client_flags: Anti-cheat flags
    - userid: Player who set the score
    - perfect: Whether it's a full combo
    - online_checksum: Anti-cheat checksum
    - pinned: Whether the score is pinned
    - cheat_values: Anti-cheat analysis data

Usage Pattern:
    # Create a new score
    score = await create(
        map_md5="abc123...",
        score=1000000,
        pp=100.5,
        acc=95.5,
        max_combo=500,
        mods=0,
        n300=300,
        n100=50,
        n50=10,
        nmiss=5,
        ngeki=0,
        nkatu=0,
        grade="A",
        status=2,
        mode=0,
        play_time=datetime.now(),
        time_elapsed=180,
        client_flags=0,
        user_id=12345,
        perfect=0,
        online_checksum="def456..."
    )
    
    # Fetch score by ID
    score = await fetch_one(id=12345)
    
    # Fetch scores with filtering
    scores = await fetch_many(
        map_md5="abc123...",
        status=2,
        mode=0,
        page=1,
        page_size=10
    )
    
    # Update score
    updated = await partial_update(
        id=12345,
        pp=150.0,
        status=2
    )

Related Files:
    - app/objects/score.py: Score data model
    - app/api/domains/osu.py: Score submission handling
    - app/usecases/performance.py: Performance calculation
    - app/objects/beatmap.py: Beatmap data for score context
    - app/objects/player.py: Player statistics tracking
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast
from typing import Optional

from sqlalchemy import Column, DateTime, Index, Integer, String, func, insert, select, update, outerjoin, and_
from sqlalchemy.dialects.mysql import FLOAT
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
import app.settings
from app.logging import Ansi, log, logLevel
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base
import json


class ScoresTable(Base):
    __tablename__ = "scores"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    map_md5 = Column("map_md5", String(32), nullable=False)
    score = Column("score", Integer, nullable=False)
    pp = Column("pp", FLOAT(precision=6, scale=3), nullable=False)
    acc = Column("acc", FLOAT(precision=6, scale=3), nullable=False)
    max_combo = Column("max_combo", Integer, nullable=False)
    mods = Column("mods", Integer, nullable=False)
    n300 = Column("n300", Integer, nullable=False)
    n100 = Column("n100", Integer, nullable=False)
    n50 = Column("n50", Integer, nullable=False)
    nmiss = Column("nmiss", Integer, nullable=False)
    ngeki = Column("ngeki", Integer, nullable=False)
    nkatu = Column("nkatu", Integer, nullable=False)
    grade = Column("grade", String(2), nullable=False, server_default="N")
    status = Column("status", Integer, nullable=False)
    mode = Column("mode", Integer, nullable=False)
    play_time = Column("play_time", DateTime, nullable=False)
    time_elapsed = Column("time_elapsed", Integer, nullable=False)
    client_flags = Column("client_flags", Integer, nullable=False)
    userid = Column("userid", Integer, nullable=False)
    perfect = Column("perfect", TINYINT(1), nullable=False)
    online_checksum = Column("online_checksum", String(32), nullable=False)
    pinned = Column("pinned", TINYINT(1), nullable=False)

    __table_args__ = (
        Index("scores_map_md5_index", map_md5),
        Index("scores_score_index", score),
        Index("scores_pp_index", pp),
        Index("scores_mods_index", mods),
        Index("scores_status_index", status),
        Index("scores_mode_index", mode),
        Index("scores_play_time_index", play_time),
        Index("scores_userid_index", userid),
        Index("scores_online_checksum_index", online_checksum),
        Index("scores_pinned_index", pinned),
    )

class ScoreInfoTable(Base):
    __tablename__ = "scoreinfo"
    
    scoreid = Column("scoreid", Integer, nullable=False, primary_key=True, autoincrement=False)
    cheat_values = Column("cheat_values", String(1024, collation="utf8mb4_general_ci"), nullable=True)
    
    __table_args__ = (
        Index("scoreinfo_scoreid_index", scoreid),
    )


READ_PARAMS = (
    ScoresTable.id,
    ScoresTable.map_md5,
    ScoresTable.score,
    ScoresTable.pp,
    ScoresTable.acc,
    ScoresTable.max_combo,
    ScoresTable.mods,
    ScoresTable.n300,
    ScoresTable.n100,
    ScoresTable.n50,
    ScoresTable.nmiss,
    ScoresTable.ngeki,
    ScoresTable.nkatu,
    ScoresTable.grade,
    ScoresTable.status,
    ScoresTable.mode,
    ScoresTable.play_time,
    ScoresTable.time_elapsed,
    ScoresTable.client_flags,
    ScoresTable.userid,
    ScoresTable.perfect,
    ScoresTable.online_checksum,
)


class Score(TypedDict):
    id: int
    map_md5: str
    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int
    mods_readable: Optional[str]
    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int
    grade: str
    status: int
    mode: int
    play_time: datetime
    time_elapsed: int
    client_flags: int
    userid: int
    perfect: int
    online_checksum: str
    pinned: int
    cheat_values: Optional[str]


async def create(
    map_md5: str,
    score: int,
    pp: float,
    acc: float,
    max_combo: int,
    mods: int,
    n300: int,
    n100: int,
    n50: int,
    nmiss: int,
    ngeki: int,
    nkatu: int,
    grade: str,
    status: int,
    mode: int,
    play_time: datetime,
    time_elapsed: int,
    client_flags: int,
    user_id: int,
    perfect: int,
    online_checksum: str,
) -> Score:
    insert_stmt = insert(ScoresTable).values(
        map_md5=map_md5,
        score=score,
        pp=pp,
        acc=acc,
        max_combo=max_combo,
        mods=mods,
        n300=n300,
        n100=n100,
        n50=n50,
        nmiss=nmiss,
        ngeki=ngeki,
        nkatu=nkatu,
        grade=grade,
        status=status,
        mode=mode,
        play_time=play_time,
        time_elapsed=time_elapsed,
        client_flags=client_flags,
        userid=user_id,
        perfect=perfect,
        online_checksum=online_checksum,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(ScoresTable.id == rec_id)
    _score = await app.state.services.database.fetch_one(select_stmt)
    assert _score is not None
    return cast(Score, _score)


async def fetch_one(id: int) -> Score | None:
    try:
        joined = outerjoin(ScoresTable, ScoreInfoTable, ScoresTable.id == ScoreInfoTable.scoreid)
        select_stmt = select(*READ_PARAMS, ScoreInfoTable.cheat_values).select_from(joined).where(ScoresTable.id == id)
        _score = await app.state.services.database.fetch_one(select_stmt)

        if _score is not None and 'cheat_values' in _score and _score['cheat_values'] is not None:
            try:
                # Handle case where cheat_values is already a JSON object (not a string)
                if isinstance(_score['cheat_values'], (dict, list)):
                    cheat_values = _score['cheat_values']
                else:
                    # Handle case where cheat_values is a JSON string
                    cheat_values = json.loads(_score['cheat_values'])
                    # Handle case where the parsed JSON is itself a JSON string
                    if isinstance(cheat_values, str):
                        cheat_values = json.loads(cheat_values)
                
                _score = dict(_score, cheat_values=cheat_values)
                log(
                    f"Fetched Score: {_score['id']}", Ansi.LYELLOW, 
                    extra={
                        "filter": {
                            "debugLevel": 2,
                            "debugFocus": "scores",
                        },
                        "Score": _score
                        },
                    logger="console.debug",
                    level=logLevel.DBGLV2)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                # If parsing fails, keep the original value and log a warning
                log(
                    f"Failed to parse cheat_values for score {id}: {e}. Keeping original value.",
                    Ansi.LYELLOW,
                    extra={
                        "score_id": id,
                        "cheat_values_raw": _score['cheat_values'],
                        "error": str(e)
                    },
                    logger="console.debug",
                    level=logLevel.DBGLV2)
        
        return cast(Score | None, _score)
    except Exception as e:
        log(
            f"An error occurred while fetching a score with id {id} | Error: {e}.",
            Ansi.LRED,
            extra={"Exception": str(e)},
            logger="console.error",
            level=logLevel.ERROR,
        )
        return None


async def fetch_count(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    season_id: int | None = None,
) -> int:
    select_stmt = select(func.count().label("count")).select_from(ScoresTable)
    if map_md5 is not None:
        select_stmt = select_stmt.where(ScoresTable.map_md5 == map_md5)
    if mods is not None:
        select_stmt = select_stmt.where(ScoresTable.mods == mods)
    if status is not None:
        select_stmt = select_stmt.where(ScoresTable.status == status)
    if mode is not None:
        select_stmt = select_stmt.where(ScoresTable.mode == mode)
    if user_id is not None:
        select_stmt = select_stmt.where(ScoresTable.userid == user_id)
    if season_id is not None:
        # JOIN with seasons table to filter by play_time within season date range
        from app.repositories.seasons import SeasonsTable
        select_stmt = select_stmt.select_from(
            ScoresTable.__table__.join(
                SeasonsTable.__table__,
                and_(
                    ScoresTable.play_time >= SeasonsTable.start_date,
                    ScoresTable.play_time < SeasonsTable.end_date,
                    SeasonsTable.id == season_id,
                ),
            )
        )

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    season_id: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Score]:
    select_stmt = select(*READ_PARAMS)
    if map_md5 is not None:
        select_stmt = select_stmt.where(ScoresTable.map_md5 == map_md5)
    if mods is not None:
        select_stmt = select_stmt.where(ScoresTable.mods == mods)
    if status is not None:
        select_stmt = select_stmt.where(ScoresTable.status == status)
    if mode is not None:
        select_stmt = select_stmt.where(ScoresTable.mode == mode)
    if user_id is not None:
        select_stmt = select_stmt.where(ScoresTable.userid == user_id)
    if season_id is not None:
        # JOIN with seasons table to filter by play_time within season date range
        from app.repositories.seasons import SeasonsTable
        select_stmt = select_stmt.select_from(
            ScoresTable.__table__.join(
                SeasonsTable.__table__,
                and_(
                    ScoresTable.play_time >= SeasonsTable.start_date,
                    ScoresTable.play_time < SeasonsTable.end_date,
                    SeasonsTable.id == season_id,
                ),
            )
        )

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    scores = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Score], scores)


async def partial_update(
    id: int,
    pp: float | _UnsetSentinel = UNSET,
    status: int | _UnsetSentinel = UNSET,
) -> Score | None:
    """Update an existing score."""
    update_stmt = update(ScoresTable).where(ScoresTable.id == id)
    if not isinstance(pp, _UnsetSentinel):
        update_stmt = update_stmt.values(pp=pp)
    if not isinstance(status, _UnsetSentinel):
        update_stmt = update_stmt.values(status=status)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(ScoresTable.id == id)
    _score = await app.state.services.database.fetch_one(select_stmt)
    return cast(Score | None, _score)


async def fetch_oldest_play_time() -> datetime | None:
    """Fetch the oldest play_time from the scores table.
    
    Returns:
        The oldest play_time datetime, or None if no scores exist.
    """
    select_stmt = select(func.min(ScoresTable.play_time).label("oldest_play_time"))
    result = await app.state.services.database.fetch_one(select_stmt)
    if result and result["oldest_play_time"]:
        return cast(datetime, result["oldest_play_time"])
    return None


# TODO: delete
