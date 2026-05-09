"""
Repositories Package - Database Access Layer Foundation

This module provides the foundational database access layer for the osu! server
application, establishing the SQLAlchemy ORM infrastructure and base classes
used by all repository modules. It initializes the mapper registry and defines
the base declarative model class that all database models inherit from.

The module serves as the entry point for the repository pattern implementation,
providing a clean separation between business logic and data access layers.
It ensures consistent database interaction patterns across all repository
modules while maintaining type safety and proper ORM integration.

Key Features:
    - SQLAlchemy ORM mapper registry initialization
    - Base declarative model class for all database models
    - Consistent database access patterns across repositories
    - Type-safe ORM integration with proper inheritance
    - Centralized database configuration management
    - Clean separation of data access and business logic

Integration Points:
    - All repository modules in app/repositories/
    - Database models for achievements, badges, channels, clans, etc.
    - SQLAlchemy ORM for database operations
    - Database connection management in app/state/services.py
    - Application state management in app/state/

Database Models:
    - Achievements: Player achievement tracking
    - Badges: Player badge management
    - Channels: Chat channel configuration
    - Clans: Player clan information
    - Client Hashes: Anti-cheat hardware tracking
    - Comments: User comment system
    - Favourites: Player favourite beatmaps
    - Ingame Logins: Login session tracking
    - Logs: Administrative action logging
    - Mail: User messaging system
    - Map Requests: Beatmap ranking requests
    - Maps: Beatmap information storage
    - Ratings: Beatmap rating system
    - Scores: Gameplay score records
    - Stats: Player statistics tracking
    - Tourney Pool Maps: Tournament map pool entries
    - Tourney Pools: Tournament pool management
    - User Achievements: Player achievement tracking
    - Users: Player account information

Usage Pattern:
    # Import the base class for new models
    from app.repositories import Base

    # Create a new database model
    class MyModel(Base):
        __tablename__ = "my_table"
        id = Column(Integer, primary_key=True)
        name = Column(String(50))

    # Use repository functions
    from app.repositories import users
    user = await users.fetch_one(id=12345)

Related Files:
    - app/repositories/achievements.py: Achievement data access
    - app/repositories/users.py: User data access
    - app/repositories/scores.py: Score data access
    - app/state/services.py: Database connection management
    - app/settings.py: Database configuration
"""

from __future__ import annotations

import sqlalchemy
from sqlalchemy.orm import DeclarativeMeta
from sqlalchemy.orm import registry

mapper_registry = registry()


class Base(metaclass=DeclarativeMeta):
    """Base class for all SQLAlchemy ORM models.

    This class provides the foundation for all database models in the
    application, establishing the mapper registry and metadata that
    SQLAlchemy uses for database operations. All repository models
    should inherit from this class to ensure consistent ORM behavior.

    Attributes:
        registry: SQLAlchemy mapper registry for model registration
        metadata: SQLAlchemy metadata for schema management
        __init__: Constructor function from the mapper registry
    """

    __abstract__ = True

    registry = mapper_registry
    metadata = mapper_registry.metadata

    __init__ = mapper_registry.constructor
    __table__: sqlalchemy.Table
