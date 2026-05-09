"""
Tourney Pools Repository - Database Operations for Tournament Pool Management

This module provides database operations for managing tournament pools in the
osu! server application. It implements the repository pattern for tournament
pool data access, providing a clean abstraction layer between the application
logic and database operations for pool storage, retrieval, and management.

The repository handles operations for storing and managing tournament pools,
which are collections of beatmaps organized for competitive tournament play.
Each pool has a name, creation timestamp, and is associated with the user
who created it, allowing for organized tournament map management.

Key Features:
    - Tournament pool creation and storage
    - Pool retrieval by ID, name, or creator
    - Timestamp tracking for pool creation
    - Creator association for ownership tracking
    - Type-safe data access with TypedDict definitions
    - Integration with tournament and map pool management systems

Integration Points:
    - Tournament management in app/objects/match.py
    - Map pool management in app/repositories/tourney_pool_maps.py
    - Tournament API in app/api/v2/tournaments.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py

Database Schema:
    - id: Primary key with auto-increment
    - name: Pool name (max 16 characters)
    - created_at: Timestamp when pool was created
    - created_by: User ID who created the pool

Tournament Pool Structure:
    - id: Unique identifier for the pool
    - name: Display name of the pool
    - created_at: When the pool was created
    - created_by: User who created the pool

Tournament Pool Features:
    - Named pools for different tournament stages
    - Creator tracking for ownership and permissions
    - Timestamp tracking for pool history
    - Integration with map pool entries for complete pool management

Usage Pattern:
    # Create a new tournament pool
    pool = await create(
        name="OWC 2023 Finals",
        created_by=admin_id
    )

    # Get pool by ID
    pool = await fetch_by_id(id=1)

    # Get pool by name
    pool = await fetch_by_name(name="OWC 2023 Finals")

    # Get pools created by a user
    pools = await fetch_many(created_by=admin_id)

    # Get pools with pagination
    pools = await fetch_many(
        page=1,
        page_size=10
    )

    # Delete a pool
    deleted = await delete_by_id(id=1)

Related Files:
    - app/repositories/tourney_pool_maps.py: Map entries for pools
    - app/objects/match.py: Match management with tournament pools
    - app/api/v2/tournaments.py: Tournament API endpoints
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


class TourneyPoolsTable(Base):
    __tablename__ = "tourney_pools"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    name = Column("name", String(16), nullable=False)
    created_at = Column("created_at", DateTime, nullable=False)
    created_by = Column("created_by", Integer, nullable=False)

    __table_args__ = (Index("tourney_pools_users_id_fk", created_by),)


class TourneyPool(TypedDict):
    id: int
    name: str
    created_at: datetime
    created_by: int


READ_PARAMS = (
    TourneyPoolsTable.id,
    TourneyPoolsTable.name,
    TourneyPoolsTable.created_at,
    TourneyPoolsTable.created_by,
)


async def create(name: str, created_by: int) -> TourneyPool:
    """Create a new tourney pool entry in the database."""
    insert_stmt = insert(TourneyPoolsTable).values(
        name=name,
        created_at=func.now(),
        created_by=created_by,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.id == rec_id)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    if tourney_pool is None:
        raise RuntimeError("Failed to fetch created tourney pool")
    return cast("TourneyPool", tourney_pool)


async def fetch_many(
    id: int | None = None,
    created_by: int | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[TourneyPool]:
    """Fetch many tourney pools from the database."""
    select_stmt = select(*READ_PARAMS)
    if id is not None:
        select_stmt = select_stmt.where(TourneyPoolsTable.id == id)
    if created_by is not None:
        select_stmt = select_stmt.where(TourneyPoolsTable.created_by == created_by)
    if page and page_size:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    tourney_pools = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[TourneyPool]", tourney_pools)


async def fetch_by_name(name: str) -> TourneyPool | None:
    """Fetch a tourney pool by name from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.name == name)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    return cast("TourneyPool | None", tourney_pool)


async def fetch_by_id(id: int) -> TourneyPool | None:
    """Fetch a tourney pool by id from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.id == id)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    return cast("TourneyPool | None", tourney_pool)


async def delete_by_id(id: int) -> TourneyPool | None:
    """Delete a tourney pool by id from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolsTable.id == id)
    tourney_pool = await app.state.services.database.fetch_one(select_stmt)
    if tourney_pool is None:
        return None

    delete_stmt = delete(TourneyPoolsTable).where(TourneyPoolsTable.id == id)
    await app.state.services.database.execute(delete_stmt)
    return cast("TourneyPool", tourney_pool)
