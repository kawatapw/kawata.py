"""
Channels Repository - Database Operations for Channel Management

This module provides database operations for managing chat channels in the osu!
server application. It implements the repository pattern for channel data access,
providing a clean abstraction layer between the application logic and database
operations for channel storage, retrieval, and management.

The repository handles all CRUD operations for channels, including creation,
retrieval, updating, and deletion of channel records. It manages both persistent
channels (like #osu) and temporary instance channels (like multiplayer and
spectator rooms) with appropriate access control settings.

Key Features:
    - Complete CRUD operations for channel data
    - Privilege-based access control management
    - Auto-join channel configuration
    - Type-safe data access with TypedDict definitions
    - Support for pagination and filtering
    - Unique constraint enforcement for channel names
    - Integration with the application state management system

Integration Points:
    - Channel management in app/objects/channel.py
    - Player channel interactions in app/objects/player.py
    - Session management in app/state/sessions.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - id: Primary key with auto-increment
    - name: Channel name (unique, max 32 characters)
    - topic: Channel topic/description (max 256 characters)
    - read_priv: Minimum privilege required to read messages
    - write_priv: Minimum privilege required to send messages
    - auto_join: Whether players automatically join this channel

Channel Types:
    - Public channels: Persistent channels like #osu, #announce
    - Private channels: Direct messages between players
    - Multiplayer channels: Temporary rooms for multiplayer matches
    - Spectator channels: Temporary rooms for spectating sessions
    - Group channels: Channels for specific player groups

Access Control:
    - read_priv: Minimum privilege required to read messages
    - write_priv: Minimum privilege required to send messages
    - Privilege checking uses bitwise AND operations
    - UNRESTRICTED privilege allows all users to access

Usage Pattern:
    # Create a new channel
    channel = await create(
        name="#osu",
        topic="General discussion",
        read_priv=Privileges.UNRESTRICTED,
        write_priv=Privileges.UNRESTRICTED,
        auto_join=True
    )

    # Fetch channel by ID or name
    channel = await fetch_one(id=1)
    channel = await fetch_one(name="#osu")

    # Fetch channels with filtering
    channels = await fetch_many(
        read_priv=Privileges.UNRESTRICTED,
        auto_join=True,
        page=1,
        page_size=10
    )

    # Update channel
    updated = await partial_update(
        name="#osu",
        topic="Updated topic"
    )

    # Delete channel
    deleted = await delete_one(name="#osu")

Related Files:
    - app/objects/channel.py: Channel data model
    - app/objects/player.py: Player channel interactions
    - app/state/sessions.py: Session management with channels
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base


class ChannelsTable(Base):
    __tablename__ = "channels"

    id = Column("id", Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column("name", String(32), nullable=False)
    topic = Column("topic", String(256), nullable=False)
    read_priv = Column("read_priv", Integer, nullable=False, server_default="1")
    write_priv = Column("write_priv", Integer, nullable=False, server_default="2")
    auto_join = Column("auto_join", TINYINT(1), nullable=False, server_default="0")

    __table_args__ = (
        Index("channels_name_uindex", name, unique=True),
        Index("channels_auto_join_index", auto_join),
    )


READ_PARAMS = (
    ChannelsTable.id,
    ChannelsTable.name,
    ChannelsTable.topic,
    ChannelsTable.read_priv,
    ChannelsTable.write_priv,
    ChannelsTable.auto_join,
)


class Channel(TypedDict):
    id: int
    name: str
    topic: str
    read_priv: int
    write_priv: int
    auto_join: bool


async def create(
    name: str,
    topic: str,
    read_priv: int,
    write_priv: int,
    auto_join: bool,
) -> Channel:
    """Create a new channel."""
    insert_stmt = insert(ChannelsTable).values(
        name=name,
        topic=topic,
        read_priv=read_priv,
        write_priv=write_priv,
        auto_join=auto_join,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(ChannelsTable.id == rec_id)
    channel = await app.state.services.database.fetch_one(select_stmt)

    if channel is None:
        raise ValueError(f"Channel with id {rec_id} not found after creation")
    return cast("Channel", channel)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Channel | None:
    """Fetch a single channel."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(ChannelsTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(ChannelsTable.name == name)

    channel = await app.state.services.database.fetch_one(select_stmt)
    return cast("Channel | None", channel)


async def fetch_count(
    read_priv: int | None = None,
    write_priv: int | None = None,
    auto_join: bool | None = None,
) -> int:
    if read_priv is None and write_priv is None and auto_join is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(func.count().label("count")).select_from(ChannelsTable)

    if read_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.read_priv == read_priv)
    if write_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.write_priv == write_priv)
    if auto_join is not None:
        select_stmt = select_stmt.where(ChannelsTable.auto_join == auto_join)

    rec = await app.state.services.database.fetch_one(select_stmt)
    if rec is None:
        raise ValueError("Failed to fetch channel count")
    return cast("int", rec["count"])


async def fetch_many(
    read_priv: int | None = None,
    write_priv: int | None = None,
    auto_join: bool | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[Channel]:
    """Fetch multiple channels from the database."""
    select_stmt = select(*READ_PARAMS)

    if read_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.read_priv == read_priv)
    if write_priv is not None:
        select_stmt = select_stmt.where(ChannelsTable.write_priv == write_priv)
    if auto_join is not None:
        select_stmt = select_stmt.where(ChannelsTable.auto_join == auto_join)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    channels = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[Channel]", channels)


async def partial_update(
    name: str,
    topic: str | _UnsetSentinel = UNSET,
    read_priv: int | _UnsetSentinel = UNSET,
    write_priv: int | _UnsetSentinel = UNSET,
    auto_join: bool | _UnsetSentinel = UNSET,
) -> Channel | None:
    """Update a channel in the database."""
    update_stmt = update(ChannelsTable).where(ChannelsTable.name == name)

    if not isinstance(topic, _UnsetSentinel):
        update_stmt = update_stmt.values(topic=topic)
    if not isinstance(read_priv, _UnsetSentinel):
        update_stmt = update_stmt.values(read_priv=read_priv)
    if not isinstance(write_priv, _UnsetSentinel):
        update_stmt = update_stmt.values(write_priv=write_priv)
    if not isinstance(auto_join, _UnsetSentinel):
        update_stmt = update_stmt.values(auto_join=auto_join)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(ChannelsTable.name == name)
    channel = await app.state.services.database.fetch_one(select_stmt)
    return cast("Channel | None", channel)


async def delete_one(
    name: str,
) -> Channel | None:
    """Delete a channel from the database."""
    select_stmt = select(*READ_PARAMS).where(ChannelsTable.name == name)
    channel = await app.state.services.database.fetch_one(select_stmt)
    if channel is None:
        return None

    delete_stmt = delete(ChannelsTable).where(ChannelsTable.name == name)
    await app.state.services.database.execute(delete_stmt)
    return cast("Channel | None", channel)
