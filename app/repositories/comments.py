"""
Comments Repository - Database Operations for User Comments

This module provides database operations for managing user comments in the osu!
server application. It implements the repository pattern for comment data access,
providing a clean abstraction layer between the application logic and database
operations for comment storage, retrieval, and management.

The repository handles operations for storing and retrieving comments on various
targets including replays, beatmaps, and songs. Comments are associated with
specific timestamps and can include optional color customization for display.

Key Features:
    - Comment creation and storage for multiple target types
    - Support for replay, beatmap, and song comments
    - Timestamp-based comment positioning
    - Optional color customization for comments
    - User privilege integration for comment display
    - Type-safe data access with TypedDict definitions
    - Integration with user management system

Integration Points:
    - Comment display in app/api/v2/players.py
    - Replay viewing in app/api/domains/osu.py
    - Beatmap display in app/api/v2/maps.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py

Database Schema:
    - id: Primary key with auto-increment
    - target_id: ID of the target (score, beatmap, or song)
    - target_type: Type of target (replay, map, or song)
    - userid: User ID who made the comment
    - time: Timestamp position in the target (float)
    - comment: Comment text (max 80 characters)
    - colour: Optional hex color code (6 characters)

Target Types:
    - REPLAY: Comments on specific replay scores
    - BEATMAP: Comments on beatmap difficulties
    - SONG: Comments on song/mapset level

Comment Structure:
    - id: Unique identifier for the comment
    - target_id: ID of the target being commented on
    - target_type: Type of target (replay, map, song)
    - userid: User who made the comment
    - time: Position in the target where comment appears
    - comment: The actual comment text
    - colour: Optional display color for the comment

Usage Pattern:
    # Create a new comment
    comment = await create(
        target_id=12345,
        target_type=TargetType.REPLAY,
        userid=67890,
        time=45.5,
        comment="Great play!",
        colour="FF0000"
    )

    # Fetch comments for a replay
    comments = await fetch_all_relevant_to_replay(
        score_id=12345,
        map_set_id=None,
        map_id=None
    )

    # Fetch comments for a beatmap
    comments = await fetch_all_relevant_to_replay(
        score_id=None,
        map_set_id=None,
        map_id=12345
    )

Related Files:
    - app/api/v2/players.py: Player profile with comments
    - app/api/domains/osu.py: Replay viewing with comments
    - app/api/v2/maps.py: Beatmap display with comments
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypedDict
from typing import cast

from sqlalchemy import CHAR
from sqlalchemy import Column
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import and_
from sqlalchemy import insert
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.mysql import FLOAT

import app.state.services
from app.repositories import Base
from app.repositories.users import UsersTable


class TargetType(StrEnum):
    REPLAY = "replay"
    BEATMAP = "map"
    SONG = "song"


class CommentsTable(Base):
    __tablename__ = "comments"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    target_id = Column("target_id", nullable=False)
    target_type = Column(Enum(TargetType, name="target_type"), nullable=False)
    userid = Column("userid", Integer, nullable=False)
    time = Column("time", FLOAT(precision=6, scale=3), nullable=False)
    comment = Column("comment", String(80, collation="utf8"), nullable=False)
    colour = Column("colour", CHAR(6), nullable=True)


READ_PARAMS = (
    CommentsTable.id,
    CommentsTable.target_id,
    CommentsTable.target_type,
    CommentsTable.userid,
    CommentsTable.time,
    CommentsTable.comment,
    CommentsTable.colour,
)


class Comment(TypedDict):
    id: int
    target_id: int
    target_type: TargetType
    userid: int
    time: float
    comment: str
    colour: str | None


async def create(
    target_id: int,
    target_type: TargetType,
    userid: int,
    time: float,
    comment: str,
    colour: str | None,
) -> Comment:
    """Create a new comment entry in the database."""
    insert_stmt = insert(CommentsTable).values(
        target_id=target_id,
        target_type=target_type,
        userid=userid,
        time=time,
        comment=comment,
        colour=colour,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(CommentsTable.id == rec_id)
    _comment = await app.state.services.database.fetch_one(select_stmt)

    if _comment is None:
        raise ValueError(f"Comment with id {rec_id} not found after creation")
    return cast("Comment", _comment)


class CommentWithUserPrivileges(Comment):
    priv: int


async def fetch_all_relevant_to_replay(
    score_id: int | None = None,
    map_set_id: int | None = None,
    map_id: int | None = None,
) -> list[CommentWithUserPrivileges]:
    """\
    Fetch all comments from the database where any of the following match:
        - `score_id`
        - `map_set_id`
        - `map_id`
    """
    select_stmt = (
        select(READ_PARAMS, UsersTable.priv)
        .join(UsersTable, CommentsTable.userid == UsersTable.id)
        .where(
            or_(
                and_(
                    CommentsTable.target_type == TargetType.REPLAY,
                    CommentsTable.target_id == score_id,
                ),
                and_(
                    CommentsTable.target_type == TargetType.SONG,
                    CommentsTable.target_id == map_set_id,
                ),
                and_(
                    CommentsTable.target_type == TargetType.BEATMAP,
                    CommentsTable.target_id == map_id,
                ),
            ),
        )
    )

    comments = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[CommentWithUserPrivileges]", comments)
