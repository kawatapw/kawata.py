"""
Map Requests Repository - Database Operations for Beatmap Ranking Requests

This module provides database operations for managing beatmap ranking requests
in the osu! server application. It implements the repository pattern for map
request data access, providing a clean abstraction layer between the application
logic and database operations for request storage, retrieval, and management.

The repository handles operations for storing and managing player requests to
have beatmaps ranked or approved. These requests are used by nominators and
moderators to track which maps players would like to see added to the ranked
pool, providing a community-driven approach to map selection.

Key Features:
    - Map request creation and storage
    - Active/inactive status tracking for requests
    - Filtering by map, player, and status
    - Batch operations for request management
    - Timestamp tracking for request timing
    - Type-safe data access with TypedDict definitions
    - Integration with beatmap and user management systems

Integration Points:
    - Map ranking system in app/api/v2/maps.py
    - Nominator tools in app/api/v2/players.py
    - Beatmap management in app/objects/beatmap.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py

Database Schema:
    - id: Primary key with auto-increment
    - map_id: Beatmap ID being requested for ranking
    - player_id: User ID who made the request
    - datetime: Timestamp when the request was made
    - active: Boolean flag indicating if request is still active

Request Structure:
    - id: Unique identifier for the request
    - map_id: Beatmap being requested for ranking
    - player_id: Player who made the request
    - datetime: When the request was made
    - active: Whether the request is still active

Request Management:
    - Players can request maps to be ranked
    - Requests can be marked as inactive when processed
    - Batch operations for handling multiple requests
    - Filtering for active requests only
    - Integration with nominator workflow

Usage Pattern:
    # Create a new map request
    request = await create(
        map_id=12345,
        player_id=67890,
        active=True
    )
    
    # Get all active requests for a map
    requests = await fetch_all(
        map_id=12345,
        active=True
    )
    
    # Get all requests by a player
    requests = await fetch_all(
        player_id=67890,
        active=None  # All requests
    )
    
    # Mark requests as inactive (when map is ranked)
    await mark_batch_as_inactive([12345, 67890])
    
    # Process requests for nominator review
    active_requests = await fetch_all(active=True)
    for request in active_requests:
        beatmap = await Beatmap.from_bid(request["map_id"])
        player = await Player.from_cache_or_sql(id=request["player_id"])
        review_request(beatmap, player)

Related Files:
    - app/api/v2/maps.py: Map ranking API endpoints
    - app/api/v2/players.py: Nominator tools and requests
    - app/objects/beatmap.py: Beatmap data model
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app.repositories import Base


class MapRequestsTable(Base):
    __tablename__ = "map_requests"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    map_id = Column("map_id", Integer, nullable=False)
    player_id = Column("player_id", Integer, nullable=False)
    datetime = Column("datetime", DateTime, nullable=False)
    active = Column("active", TINYINT(1), nullable=False)


READ_PARAMS = (
    MapRequestsTable.id,
    MapRequestsTable.map_id,
    MapRequestsTable.player_id,
    MapRequestsTable.datetime,
)


class MapRequest(TypedDict):
    id: int
    map_id: int
    player_id: int
    datetime: datetime
    active: bool


async def create(
    map_id: int,
    player_id: int,
    active: bool,
) -> MapRequest:
    """Create a new map request entry in the database."""
    insert_stmt = insert(MapRequestsTable).values(
        map_id=map_id,
        player_id=player_id,
        datetime=func.now(),
        active=active,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(MapRequestsTable.id == rec_id)
    map_request = await app.state.services.database.fetch_one(select_stmt)
    assert map_request is not None

    return cast(MapRequest, map_request)


async def fetch_all(
    map_id: int | None = None,
    player_id: int | None = None,
    active: bool | None = None,
) -> list[MapRequest]:
    """Fetch a list of map requests from the database."""
    select_stmt = select(*READ_PARAMS)
    if map_id is not None:
        select_stmt = select_stmt.where(MapRequestsTable.map_id == map_id)
    if player_id is not None:
        select_stmt = select_stmt.where(MapRequestsTable.player_id == player_id)
    if active is not None:
        select_stmt = select_stmt.where(MapRequestsTable.active == active)

    map_requests = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[MapRequest], map_requests)


async def mark_batch_as_inactive(map_ids: list[Any]) -> list[MapRequest]:
    """Mark a map request as inactive."""
    update_stmt = (
        update(MapRequestsTable)
        .where(MapRequestsTable.map_id.in_(map_ids))
        .values(active=False)
    )
    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(MapRequestsTable.map_id.in_(map_ids))
    map_requests = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[MapRequest], map_requests)
