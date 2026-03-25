"""
Ratings Repository - Database Operations for Beatmap Rating System

This module provides database operations for managing beatmap ratings in the
osu! server application. It implements the repository pattern for rating data
access, providing a clean abstraction layer between the application logic and
database operations for rating storage, retrieval, and management.

The repository handles operations for storing and retrieving player ratings
for beatmaps, allowing players to rate maps on a scale and providing feedback
to map creators and the community. Ratings are stored as simple user-map
associations with numerical rating values.

Key Features:
    - Rating creation and storage for user-map pairs
    - Rating retrieval with filtering and pagination
    - Individual rating lookup for specific user-map combinations
    - Type-safe data access with TypedDict definitions
    - Integration with beatmap and user management systems
    - Support for rating aggregation and statistics

Integration Points:
    - Rating display in app/api/v2/maps.py
    - Beatmap management in app/objects/beatmap.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - userid: User ID (foreign key to users table)
    - map_md5: Beatmap MD5 hash (foreign key to maps table)
    - rating: Numerical rating value (TINYINT, 2 digits)

Rating Structure:
    - userid: User who gave the rating
    - map_md5: Beatmap that was rated
    - rating: Numerical rating value

Rating System:
    - Players can rate beatmaps on a numerical scale
    - Ratings are stored per user per map
    - Support for rating aggregation and statistics
    - Integration with beatmap quality metrics

Usage Pattern:
    # Create a new rating
    rating = await create(
        userid=12345,
        map_md5="abc123...",
        rating=8
    )

    # Get all ratings for a user
    ratings = await fetch_many(
        userid=12345,
        page=1,
        page_size=10
    )

    # Get all ratings for a map
    ratings = await fetch_many(
        map_md5="abc123...",
        page=1,
        page_size=10
    )

    # Get specific user's rating for a map
    rating = await fetch_one(
        userid=12345,
        map_md5="abc123..."
    )

    # Calculate average rating for a map
    ratings = await fetch_many(map_md5="abc123...")
    if ratings:
        avg_rating = sum(r["rating"] for r in ratings) / len(ratings)

Related Files:
    - app/api/v2/maps.py: Map API endpoints with ratings
    - app/objects/beatmap.py: Beatmap data model
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict, cast

from sqlalchemy import Column, Integer, String, insert, select
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app.repositories import Base


class RatingsTable(Base):
    __tablename__ = "ratings"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    map_md5 = Column("map_md5", String(32), nullable=False, primary_key=True)
    rating = Column("rating", TINYINT(2), nullable=False)


READ_PARAMS = (
    RatingsTable.userid,
    RatingsTable.map_md5,
    RatingsTable.rating,
)


class Rating(TypedDict):
    userid: int
    map_md5: str
    rating: int


async def create(userid: int, map_md5: str, rating: int) -> Rating:
    """Create a new rating."""
    insert_stmt = insert(RatingsTable).values(
        userid=userid,
        map_md5=map_md5,
        rating=rating,
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(RatingsTable.userid == userid)
        .where(RatingsTable.map_md5 == map_md5)
    )
    _rating = await app.state.services.database.fetch_one(select_stmt)
    assert _rating is not None
    return cast(Rating, _rating)


async def fetch_many(
    userid: int | None = None,
    map_md5: str | None = None,
    page: int | None = 1,
    page_size: int | None = 50,
) -> list[Rating]:
    """Fetch multiple ratings, optionally with filter params and pagination."""
    select_stmt = select(*READ_PARAMS)
    if userid is not None:
        select_stmt = select_stmt.where(RatingsTable.userid == userid)
    if map_md5 is not None:
        select_stmt = select_stmt.where(RatingsTable.map_md5 == map_md5)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    ratings = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[Rating], ratings)


async def fetch_one(userid: int, map_md5: str) -> Rating | None:
    """Fetch a single rating for a given user and map."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(RatingsTable.userid == userid)
        .where(RatingsTable.map_md5 == map_md5)
    )
    rating = await app.state.services.database.fetch_one(select_stmt)
    return cast(Rating | None, rating)
