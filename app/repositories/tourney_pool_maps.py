"""
Tourney Pool Maps Repository - Database Operations for Tournament Map Pool Management

This module provides database operations for managing tournament map pool entries
in the osu! server application. It implements the repository pattern for tournament
pool map data access, providing a clean abstraction layer between the application
logic and database operations for map pool storage, retrieval, and management.

The repository handles operations for storing and managing beatmaps that are part
of tournament map pools. Each entry represents a specific beatmap with associated
mods and slot information, allowing tournament organizers to create structured
map pools for competitive play.

Key Features:
    - Map pool entry creation and storage
    - Pool-based map organization and retrieval
    - Mod and slot-based filtering for map selection
    - Batch operations for pool management
    - Type-safe data access with TypedDict definitions
    - Integration with tournament and beatmap management systems

Integration Points:
    - Tournament management in app/objects/match.py
    - Map pool handling in app/api/v2/tournaments.py
    - Beatmap management in app/objects/beatmap.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - map_id: Beatmap ID (foreign key to maps table)
    - pool_id: Tournament pool ID (foreign key to tourney_pools table)
    - mods: Bitwise mods applied to the map
    - slot: Slot position in the pool (for ordering)

Map Pool Entry Structure:
    - map_id: Beatmap identifier
    - pool_id: Tournament pool identifier
    - mods: Mods applied to the map
    - slot: Position/slot in the pool

Tournament Map Pool Features:
    - Organized map pools for tournament play
    - Mod combinations for competitive balance
    - Slot-based ordering for consistent presentation
    - Pool-based organization for different tournament stages

Usage Pattern:
    # Add a map to a pool
    pool_map = await create(
        map_id=12345,
        pool_id=1,
        mods=0,
        slot=1
    )

    # Get all maps in a pool
    maps = await fetch_many(pool_id=1)

    # Get maps by mod and slot
    maps = await fetch_many(
        pool_id=1,
        mods=0,
        slot=1
    )

    # Get specific map by pool and pick
    pool_map = await fetch_by_pool_and_pick(
        pool_id=1,
        mods=0,
        slot=1
    )

    # Remove a map from a pool
    deleted = await delete_map_from_pool(
        pool_id=1,
        map_id=12345
    )

    # Clear entire pool
    deleted_maps = await delete_all_in_pool(pool_id=1)

Related Files:
    - app/objects/match.py: Match management with tournament pools
    - app/api/v2/tournaments.py: Tournament API endpoints
    - app/objects/beatmap.py: Beatmap data model
    - app/repositories/tourney_pools.py: Tournament pool management
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import delete
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


class TourneyPoolMapsTable(Base):
    __tablename__ = "tourney_pool_maps"

    map_id = Column("map_id", Integer, nullable=False, primary_key=True)
    pool_id = Column("pool_id", Integer, nullable=False, primary_key=True)
    mods = Column("mods", Integer, nullable=False)
    slot = Column("slot", Integer, nullable=False)

    __table_args__ = (
        Index("tourney_pool_maps_mods_slot_index", mods, slot),
        Index("tourney_pool_maps_tourney_pools_id_fk", pool_id),
    )


READ_PARAMS = (
    TourneyPoolMapsTable.map_id,
    TourneyPoolMapsTable.pool_id,
    TourneyPoolMapsTable.mods,
    TourneyPoolMapsTable.slot,
)


class TourneyPoolMap(TypedDict):
    map_id: int
    pool_id: int
    mods: int
    slot: int


async def create(map_id: int, pool_id: int, mods: int, slot: int) -> TourneyPoolMap:
    """Create a new map pool entry in the database."""
    insert_stmt = insert(TourneyPoolMapsTable).values(
        map_id=map_id,
        pool_id=pool_id,
        mods=mods,
        slot=slot,
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(TourneyPoolMapsTable.map_id == map_id)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
    )
    tourney_pool_map = await app.state.services.database.fetch_one(select_stmt)
    if tourney_pool_map is None:
        raise RuntimeError("Failed to fetch tourney pool map")
    return cast("TourneyPoolMap", tourney_pool_map)


async def fetch_many(
    pool_id: int | None = None,
    mods: int | None = None,
    slot: int | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[TourneyPoolMap]:
    """Fetch a list of map pool entries from the database."""
    select_stmt = select(*READ_PARAMS)
    if pool_id is not None:
        select_stmt = select_stmt.where(TourneyPoolMapsTable.pool_id == pool_id)
    if mods is not None:
        select_stmt = select_stmt.where(TourneyPoolMapsTable.mods == mods)
    if slot is not None:
        select_stmt = select_stmt.where(TourneyPoolMapsTable.slot == slot)
    if page and page_size:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    tourney_pool_maps = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[TourneyPoolMap]", tourney_pool_maps)


async def fetch_by_pool_and_pick(
    pool_id: int,
    mods: int,
    slot: int,
) -> TourneyPoolMap | None:
    """Fetch a map pool entry by pool and pick from the database."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
        .where(TourneyPoolMapsTable.mods == mods)
        .where(TourneyPoolMapsTable.slot == slot)
    )
    tourney_pool_map = await app.state.services.database.fetch_one(select_stmt)
    return cast("TourneyPoolMap | None", tourney_pool_map)


async def delete_map_from_pool(pool_id: int, map_id: int) -> TourneyPoolMap | None:
    """Delete a map pool entry from a given tourney pool from the database."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
        .where(TourneyPoolMapsTable.map_id == map_id)
    )

    tourney_pool_map = await app.state.services.database.fetch_one(select_stmt)
    if tourney_pool_map is None:
        return None

    delete_stmt = (
        delete(TourneyPoolMapsTable)
        .where(TourneyPoolMapsTable.pool_id == pool_id)
        .where(TourneyPoolMapsTable.map_id == map_id)
    )

    await app.state.services.database.execute(delete_stmt)
    return cast("TourneyPoolMap", tourney_pool_map)


async def delete_all_in_pool(pool_id: int) -> list[TourneyPoolMap]:
    """Delete all map pool entries from a given tourney pool from the database."""
    select_stmt = select(*READ_PARAMS).where(TourneyPoolMapsTable.pool_id == pool_id)
    tourney_pool_maps = await app.state.services.database.fetch_all(select_stmt)
    if not tourney_pool_maps:
        return []

    delete_stmt = delete(TourneyPoolMapsTable).where(
        TourneyPoolMapsTable.pool_id == pool_id,
    )
    await app.state.services.database.execute(delete_stmt)
    return cast("list[TourneyPoolMap]", tourney_pool_maps)
