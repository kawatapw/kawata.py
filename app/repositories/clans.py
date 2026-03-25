"""
Clans Repository - Database Operations for Clan Management

This module provides database operations for managing player clans in the osu!
server application. It implements the repository pattern for clan data access,
providing a clean abstraction layer between the application logic and database
operations for clan storage, retrieval, and management.

The repository handles all CRUD operations for clans, including creation,
retrieval, updating, and deletion of clan records. Clans are social groups
that players can create and join, providing a sense of community and
collaboration within the osu! server.

Key Features:
    - Complete CRUD operations for clan data
    - Unique constraint enforcement for clan names and tags
    - Owner-based clan management
    - Type-safe data access with TypedDict definitions
    - Support for pagination and filtering
    - Creation timestamp tracking
    - Integration with the application state management system

Integration Points:
    - Clan management in app/api/v2/clans.py
    - Player clan membership in app/objects/player.py
    - Clan privileges in app/constants/privileges.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - id: Primary key with auto-increment
    - name: Clan display name (max 16 characters)
    - tag: Clan tag for display (max 6 characters, unique)
    - owner: Player ID of the clan owner (unique)
    - created_at: Timestamp of clan creation

Clan Structure:
    - id: Unique identifier for the clan
    - name: Display name of the clan
    - tag: Short tag for clan identification
    - owner: Player ID of the clan owner
    - created_at: When the clan was created

Clan Management:
    - Clans are created by players who become the owner
    - Only one clan per owner (enforced by unique constraint)
    - Clan tags must be unique across all clans
    - Clan names are not unique (multiple clans can have same name)

Usage Pattern:
    # Create a new clan
    clan = await create(
        name="My Clan",
        tag="MC",
        owner=player_id
    )

    # Fetch clan by ID, name, tag, or owner
    clan = await fetch_one(id=1)
    clan = await fetch_one(name="My Clan")
    clan = await fetch_one(tag="MC")
    clan = await fetch_one(owner=player_id)

    # Fetch clans with pagination
    clans = await fetch_many(page=1, page_size=10)

    # Update clan
    updated = await partial_update(
        id=1,
        name="Updated Clan Name"
    )

    # Delete clan
    deleted = await delete_one(id=1)

Related Files:
    - app/api/v2/clans.py: Clan API endpoints
    - app/objects/player.py: Player clan membership
    - app/constants/privileges.py: Clan privilege management
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict, cast

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    delete,
    func,
    insert,
    select,
    update,
)

import app.state.services
from app._typing import UNSET, _UnsetSentinel
from app.repositories import Base


class ClansTable(Base):
    __tablename__ = "clans"

    id = Column("id", Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column("name", String(16, collation="utf8"), nullable=False)
    tag = Column("tag", String(6, collation="utf8"), nullable=False)
    owner = Column("owner", Integer, nullable=False)
    created_at = Column("created_at", DateTime, nullable=False)

    __table_args__ = (
        Index("clans_name_uindex", name, unique=False),
        Index("clans_owner_uindex", owner, unique=True),
        Index("clans_tag_uindex", tag, unique=True),
    )


READ_PARAMS = (
    ClansTable.id,
    ClansTable.name,
    ClansTable.tag,
    ClansTable.owner,
    ClansTable.created_at,
)


class Clan(TypedDict):
    id: int
    name: str
    tag: str
    owner: int
    created_at: datetime


async def create(
    name: str,
    tag: str,
    owner: int,
) -> Clan:
    """Create a new clan in the database."""
    insert_stmt = insert(ClansTable).values(
        name=name,
        tag=tag,
        owner=owner,
        created_at=func.now(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(ClansTable.id == rec_id)
    clan = await app.state.services.database.fetch_one(select_stmt)

    assert clan is not None
    return cast(Clan, clan)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    tag: str | None = None,
    owner: int | None = None,
) -> Clan | None:
    """Fetch a single clan from the database."""
    if id is None and name is None and tag is None and owner is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(ClansTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(ClansTable.name == name)
    if tag is not None:
        select_stmt = select_stmt.where(ClansTable.tag == tag)
    if owner is not None:
        select_stmt = select_stmt.where(ClansTable.owner == owner)

    clan = await app.state.services.database.fetch_one(select_stmt)
    return cast(Clan | None, clan)


async def fetch_count() -> int:
    """Fetch the number of clans in the database."""
    select_stmt = select(func.count().label("count")).select_from(ClansTable)
    rec = await app.state.services.database.fetch_one(select_stmt)

    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Clan]:
    """Fetch many clans from the database."""
    select_stmt = select(*READ_PARAMS)
    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    clans = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Clan], clans)


async def partial_update(
    id: int,
    name: str | _UnsetSentinel = UNSET,
    tag: str | _UnsetSentinel = UNSET,
    owner: int | _UnsetSentinel = UNSET,
) -> Clan | None:
    """Update a clan in the database."""
    update_stmt = update(ClansTable).where(ClansTable.id == id)
    if not isinstance(name, _UnsetSentinel):
        update_stmt = update_stmt.values(name=name)
    if not isinstance(tag, _UnsetSentinel):
        update_stmt = update_stmt.values(tag=tag)
    if not isinstance(owner, _UnsetSentinel):
        update_stmt = update_stmt.values(owner=owner)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(ClansTable.id == id)
    clan = await app.state.services.database.fetch_one(select_stmt)
    return cast(Clan | None, clan)


async def delete_one(id: int) -> Clan | None:
    """Delete a clan from the database."""
    select_stmt = select(*READ_PARAMS).where(ClansTable.id == id)
    clan = await app.state.services.database.fetch_one(select_stmt)
    if clan is None:
        return None

    delete_stmt = delete(ClansTable).where(ClansTable.id == id)
    await app.state.services.database.execute(delete_stmt)
    return cast(Clan, clan)
