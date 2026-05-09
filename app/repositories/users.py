"""
Users Repository - Database Operations for User Account Management

This module provides database operations for managing user accounts in the
osu! server application. It implements the repository pattern for user data
access, providing a clean abstraction layer between the application logic
and database operations for user storage, retrieval, and management.

The repository handles all CRUD operations for user accounts, including
creation, retrieval, updating, and management of user records. It supports
comprehensive user data including authentication, profile information,
privileges, clan membership, and customization options.

Key Features:
    - Complete CRUD operations for user accounts
    - Secure password storage with bcrypt hashing
    - Privilege-based access control management
    - Clan membership and role tracking
    - Profile customization (badges, userpage content)
    - API key management for external integrations
    - Country and timezone tracking
    - Silence and donor status management
    - Type-safe data access with TypedDict definitions

Integration Points:
    - Authentication in app/api/domains/cho.py
    - Player management in app/objects/player.py
    - Privilege system in app/constants/privileges.py
    - Clan management in app/repositories/clans.py
    - Database connection in app/state/services.py

Database Schema:
    - id: Primary key with auto-increment
    - name: Display name (unique, max 32 characters)
    - safe_name: URL-safe version of name (unique, max 32 characters)
    - email: Email address (unique, max 254 characters)
    - priv: Bitwise privilege flags
    - pw_bcrypt: Bcrypt hashed password (60 characters)
    - country: Two-letter country code
    - silence_end: Unix timestamp when silence ends
    - donor_end: Unix timestamp when donor status ends
    - creation_time: Unix timestamp when account was created
    - latest_activity: Unix timestamp of last activity
    - clan_id: Clan ID (0 if not in clan)
    - clan_priv: Clan privilege level
    - preferred_mode: Preferred game mode
    - play_style: Play style preferences
    - custom_badge_name: Custom badge name (max 16 characters)
    - custom_badge_icon: Custom badge icon URL (max 64 characters)
    - userpage_content: User profile content (max 2048 characters)
    - api_key: API key for external access (36 characters, unique)

User Structure:
    - id: Unique identifier
    - name: Display name
    - safe_name: URL-safe name
    - email: Email address
    - priv: Privilege flags
    - pw_bcrypt: Hashed password
    - country: Country code
    - silence_end: Silence end timestamp
    - donor_end: Donor end timestamp
    - creation_time: Account creation timestamp
    - latest_activity: Last activity timestamp
    - clan_id: Clan membership
    - clan_priv: Clan privileges
    - preferred_mode: Preferred game mode
    - play_style: Play style preferences
    - custom_badge_name: Custom badge name
    - custom_badge_icon: Custom badge icon
    - userpage_content: Profile content
    - api_key: API access key

Usage Pattern:
    # Create a new user
    user = await create(
        name="PlayerName",
        email="player@example.com",
        pw_bcrypt=hashed_password,
        country="US"
    )

    # Fetch user by ID, name, or email
    user = await fetch_one(id=12345)
    user = await fetch_one(name="PlayerName")
    user = await fetch_one(email="player@example.com")

    # Fetch users with filtering
    users = await fetch_many(
        priv=Privileges.UNRESTRICTED,
        country="US",
        page=1,
        page_size=10
    )

    # Update user
    updated = await partial_update(
        id=12345,
        priv=Privileges.SUPPORTER,
        donor_end=int(time.time()) + 86400
    )

Related Files:
    - app/objects/player.py: Player class with user data
    - app/api/domains/cho.py: Client authentication
    - app/constants/privileges.py: Privilege system
    - app/repositories/clans.py: Clan management
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base
from app.utils import make_safe_name


class UsersTable(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    name = Column(String(32, collation="utf8"), nullable=False)
    safe_name = Column(String(32, collation="utf8"), nullable=False)
    email = Column(String(254), nullable=False)
    priv = Column(Integer, nullable=False, server_default="1")
    pw_bcrypt = Column(String(60), nullable=False)
    country = Column(String(2), nullable=False, server_default="xx")
    silence_end = Column(Integer, nullable=False, server_default="0")
    donor_end = Column(Integer, nullable=False, server_default="0")
    creation_time = Column(Integer, nullable=False, server_default="0")
    latest_activity = Column(Integer, nullable=False, server_default="0")
    clan_id = Column(Integer, nullable=False, server_default="0")
    clan_priv = Column(TINYINT, nullable=False, server_default="0")
    preferred_mode = Column(Integer, nullable=False, server_default="0")
    play_style = Column(Integer, nullable=False, server_default="0")
    custom_badge_name = Column(String(16, collation="utf8"))
    custom_badge_icon = Column(String(64))
    userpage_content = Column(String(2048, collation="utf8"))
    api_key = Column(String(36))
    preferred_lb_view = Column(String(16), nullable=False, server_default="all_time")
    preferred_schedule_id = Column(Integer, nullable=True)

    __table_args__ = (
        Index("users_priv_index", priv),
        Index("users_clan_id_index", clan_id),
        Index("users_clan_priv_index", clan_priv),
        Index("users_country_index", country),
        Index("users_api_key_uindex", api_key, unique=True),
        Index("users_email_uindex", email, unique=True),
        Index("users_name_uindex", name, unique=True),
        Index("users_safe_name_uindex", safe_name, unique=True),
    )


READ_PARAMS = (
    UsersTable.id,
    UsersTable.name,
    UsersTable.safe_name,
    UsersTable.priv,
    UsersTable.country,
    UsersTable.silence_end,
    UsersTable.donor_end,
    UsersTable.creation_time,
    UsersTable.latest_activity,
    UsersTable.clan_id,
    UsersTable.clan_priv,
    UsersTable.preferred_mode,
    UsersTable.play_style,
    UsersTable.custom_badge_name,
    UsersTable.custom_badge_icon,
    UsersTable.userpage_content,
    UsersTable.preferred_lb_view,
    UsersTable.preferred_schedule_id,
)


class User(TypedDict):
    id: int
    name: str
    safe_name: str
    priv: int
    pw_bcrypt: str
    country: str
    silence_end: int
    donor_end: int
    creation_time: int
    latest_activity: int
    clan_id: int
    clan_priv: int
    preferred_mode: int
    play_style: int
    custom_badge_name: str | None
    custom_badge_icon: str | None
    userpage_content: str | None
    api_key: str | None
    preferred_lb_view: str
    preferred_schedule_id: int | None


async def create(
    name: str,
    email: str,
    pw_bcrypt: bytes,
    country: str,
) -> User:
    """Create a new user in the database."""
    insert_stmt = insert(UsersTable).values(
        name=name,
        safe_name=make_safe_name(name),
        email=email,
        pw_bcrypt=pw_bcrypt,
        country=country,
        creation_time=func.unix_timestamp(),
        latest_activity=func.unix_timestamp(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(UsersTable.id == rec_id)
    user = await app.state.services.database.fetch_one(select_stmt)
    if user is None:
        raise RuntimeError("Failed to fetch created user")
    return cast("User", user)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    email: str | None = None,
    fetch_all_fields: bool = False,  # TODO: probably remove this if possible
) -> User | None:
    """Fetch a single user from the database."""
    if id is None and name is None and email is None:
        raise ValueError("Must provide at least one parameter.")

    if fetch_all_fields:
        select_stmt = select(UsersTable)
    else:
        select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(UsersTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(UsersTable.safe_name == make_safe_name(name))
    if email is not None:
        select_stmt = select_stmt.where(UsersTable.email == email)

    user = await app.state.services.database.fetch_one(select_stmt)
    return cast("User | None", user)


async def fetch_count(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
) -> int:
    """Fetch the number of users in the database."""
    select_stmt = select(func.count().label("count")).select_from(UsersTable)
    if priv is not None:
        select_stmt = select_stmt.where(UsersTable.priv == priv)
    if country is not None:
        select_stmt = select_stmt.where(UsersTable.country == country)
    if clan_id is not None:
        select_stmt = select_stmt.where(UsersTable.clan_id == clan_id)
    if clan_priv is not None:
        select_stmt = select_stmt.where(UsersTable.clan_priv == clan_priv)
    if preferred_mode is not None:
        select_stmt = select_stmt.where(UsersTable.preferred_mode == preferred_mode)
    if play_style is not None:
        select_stmt = select_stmt.where(UsersTable.play_style == play_style)

    rec = await app.state.services.database.fetch_one(select_stmt)
    if rec is None:
        raise RuntimeError("Failed to fetch users count")
    return cast("int", rec["count"])


async def fetch_many(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[User]:
    """Fetch multiple users from the database."""
    select_stmt = select(*READ_PARAMS)
    if priv is not None:
        select_stmt = select_stmt.where(UsersTable.priv == priv)
    if country is not None:
        select_stmt = select_stmt.where(UsersTable.country == country)
    if clan_id is not None:
        select_stmt = select_stmt.where(UsersTable.clan_id == clan_id)
    if clan_priv is not None:
        select_stmt = select_stmt.where(UsersTable.clan_priv == clan_priv)
    if preferred_mode is not None:
        select_stmt = select_stmt.where(UsersTable.preferred_mode == preferred_mode)
    if play_style is not None:
        select_stmt = select_stmt.where(UsersTable.play_style == play_style)

    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    users = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[User]", users)


async def partial_update(
    id: int,
    name: str | _UnsetSentinel = UNSET,
    email: str | _UnsetSentinel = UNSET,
    priv: int | _UnsetSentinel = UNSET,
    country: str | _UnsetSentinel = UNSET,
    silence_end: int | _UnsetSentinel = UNSET,
    donor_end: int | _UnsetSentinel = UNSET,
    creation_time: _UnsetSentinel | _UnsetSentinel = UNSET,
    latest_activity: int | _UnsetSentinel = UNSET,
    clan_id: int | _UnsetSentinel = UNSET,
    clan_priv: int | _UnsetSentinel = UNSET,
    preferred_mode: int | _UnsetSentinel = UNSET,
    play_style: int | _UnsetSentinel = UNSET,
    custom_badge_name: str | None | _UnsetSentinel = UNSET,
    custom_badge_icon: str | None | _UnsetSentinel = UNSET,
    userpage_content: str | None | _UnsetSentinel = UNSET,
    api_key: str | None | _UnsetSentinel = UNSET,
    preferred_lb_view: str | _UnsetSentinel = UNSET,
    preferred_schedule_id: int | None | _UnsetSentinel = UNSET,
) -> User | None:
    """Update a user in the database."""
    update_stmt = update(UsersTable).where(UsersTable.id == id)
    if not isinstance(name, _UnsetSentinel):
        update_stmt = update_stmt.values(name=name, safe_name=make_safe_name(name))
    if not isinstance(email, _UnsetSentinel):
        update_stmt = update_stmt.values(email=email)
    if not isinstance(priv, _UnsetSentinel):
        update_stmt = update_stmt.values(priv=priv)
    if not isinstance(country, _UnsetSentinel):
        update_stmt = update_stmt.values(country=country)
    if not isinstance(silence_end, _UnsetSentinel):
        update_stmt = update_stmt.values(silence_end=silence_end)
    if not isinstance(donor_end, _UnsetSentinel):
        update_stmt = update_stmt.values(donor_end=donor_end)
    if not isinstance(creation_time, _UnsetSentinel):
        update_stmt = update_stmt.values(creation_time=creation_time)
    if not isinstance(latest_activity, _UnsetSentinel):
        update_stmt = update_stmt.values(latest_activity=latest_activity)
    if not isinstance(clan_id, _UnsetSentinel):
        update_stmt = update_stmt.values(clan_id=clan_id)
    if not isinstance(clan_priv, _UnsetSentinel):
        update_stmt = update_stmt.values(clan_priv=clan_priv)
    if not isinstance(preferred_mode, _UnsetSentinel):
        update_stmt = update_stmt.values(preferred_mode=preferred_mode)
    if not isinstance(play_style, _UnsetSentinel):
        update_stmt = update_stmt.values(play_style=play_style)
    if not isinstance(custom_badge_name, _UnsetSentinel):
        update_stmt = update_stmt.values(custom_badge_name=custom_badge_name)
    if not isinstance(custom_badge_icon, _UnsetSentinel):
        update_stmt = update_stmt.values(custom_badge_icon=custom_badge_icon)
    if not isinstance(userpage_content, _UnsetSentinel):
        update_stmt = update_stmt.values(userpage_content=userpage_content)
    if not isinstance(api_key, _UnsetSentinel):
        update_stmt = update_stmt.values(api_key=api_key)
    if not isinstance(preferred_lb_view, _UnsetSentinel):
        update_stmt = update_stmt.values(preferred_lb_view=preferred_lb_view)
    if not isinstance(preferred_schedule_id, _UnsetSentinel):
        update_stmt = update_stmt.values(preferred_schedule_id=preferred_schedule_id)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(UsersTable.id == id)
    user = await app.state.services.database.fetch_one(select_stmt)
    return cast("User | None", user)


# TODO: delete?
