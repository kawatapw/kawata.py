"""
Favourites Repository - Database Operations for User Favourite Mapsets

This module provides database operations for managing user favourite mapsets
in the osu! server application. It implements the repository pattern for
favourite data access, providing a clean abstraction layer between the
application logic and database operations for favourite storage and retrieval.

The repository handles operations for storing and retrieving user's favourite
beatmap sets, allowing players to bookmark and quickly access their preferred
content. Favourites are stored as simple user-mapset associations with
timestamps for tracking when they were added.

Key Features:
    - Favourite creation and storage for user-mapset pairs
    - Timestamp tracking for when favourites were added
    - Bulk retrieval of all favourites for a user
    - Individual favourite lookup for specific mapsets
    - Type-safe data access with TypedDict definitions
    - Integration with user and beatmap management systems

Integration Points:
    - Favourite display in app/api/v2/players.py
    - Beatmap set management in app/objects/beatmap.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - userid: User ID (foreign key to users table)
    - setid: Beatmap set ID (foreign key to mapsets table)
    - created_at: Unix timestamp when favourite was added

Favourite Structure:
    - userid: User who added the favourite
    - setid: Beatmap set that was favourited
    - created_at: When the favourite was added (Unix timestamp)

Usage Pattern:
    # Add a favourite
    favourite = await create(
        userid=12345,
        setid=67890
    )
    
    # Get all favourites for a user
    favourites = await fetch_all(userid=12345)
    
    # Check if a specific mapset is favourited
    favourite = await fetch_one(
        userid=12345,
        setid=67890
    )
    
    # Process favourites for display
    for fav in favourites:
        beatmap_set = await BeatmapSet.from_bsid(fav["setid"])
        display_favourite(beatmap_set, fav["created_at"])

Related Files:
    - app/api/v2/players.py: Player profile with favourites
    - app/objects/beatmap.py: Beatmap set management
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


class FavouritesTable(Base):
    __tablename__ = "favourites"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    setid = Column("setid", Integer, nullable=False, primary_key=True)
    created_at = Column("created_at", Integer, nullable=False, server_default="0")


READ_PARAMS = (
    FavouritesTable.userid,
    FavouritesTable.setid,
    FavouritesTable.created_at,
)


class Favourite(TypedDict):
    userid: int
    setid: int
    created_at: int


async def create(
    userid: int,
    setid: int,
) -> Favourite:
    """Create a new favourite mapset entry in the database."""
    insert_stmt = insert(FavouritesTable).values(
        userid=userid,
        setid=setid,
        created_at=func.unix_timestamp(),
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(FavouritesTable.userid == userid)
        .where(FavouritesTable.setid == setid)
    )
    favourite = await app.state.services.database.fetch_one(select_stmt)

    assert favourite is not None
    return cast(Favourite, favourite)


async def fetch_all(userid: int) -> list[Favourite]:
    """Fetch all favourites from a player."""
    select_stmt = select(*READ_PARAMS).where(FavouritesTable.userid == userid)
    favourites = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Favourite], favourites)


async def fetch_one(userid: int, setid: int) -> Favourite | None:
    """Check if a mapset is already a favourite."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(FavouritesTable.userid == userid)
        .where(FavouritesTable.setid == setid)
    )
    favourite = await app.state.services.database.fetch_one(select_stmt)
    return cast(Favourite | None, favourite)
