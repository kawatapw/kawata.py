"""
Ingame Logins Repository - Database Operations for Login Tracking

This module provides database operations for tracking player login sessions
in the osu! server application. It implements the repository pattern for login
data access, providing a clean abstraction layer between the application logic
and database operations for login session storage and retrieval.

The repository handles operations for storing and retrieving player login
information, including IP addresses, osu! client versions, and timestamps.
This data is used for security monitoring, analytics, and anti-cheat purposes.

Key Features:
    - Login session tracking with IP and client information
    - osu! version and stream tracking for analytics
    - Timestamp recording for session analysis
    - Filtering by user, IP, version, and stream
    - Pagination support for large datasets
    - Type-safe data access with TypedDict definitions
    - Integration with user management system

Integration Points:
    - Login handling in app/api/domains/cho.py
    - Security monitoring in app/usecases/achievements.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - id: Primary key with auto-increment
    - userid: User ID (foreign key to users table)
    - ip: IP address of the connection (max 45 chars for IPv6)
    - osu_ver: Date of the osu! client version
    - osu_stream: Stream identifier (stable, beta, cuttingedge, etc.)
    - datetime: Timestamp when the login occurred

Login Information:
    - userid: User who logged in
    - ip: IP address used for the connection
    - osu_ver: Date component of osu! client version
    - osu_stream: Client stream (stable, beta, cuttingedge, tourney, dev, Aeris)
    - datetime: When the login occurred

Security Features:
    - IP tracking for suspicious activity detection
    - Version tracking for client validation
    - Stream tracking for client type identification
    - Session timing analysis for pattern detection

Usage Pattern:
    # Record a new login
    login = await create(
        user_id=12345,
        ip="192.168.1.1",
        osu_ver=date(2023, 12, 15),
        osu_stream="stable"
    )

    # Get login count for a user
    count = await fetch_count(user_id=12345)

    # Get login count for an IP
    count = await fetch_count(ip="192.168.1.1")

    # Get logins with filtering
    logins = await fetch_many(
        user_id=12345,
        osu_stream="stable",
        page=1,
        page_size=10
    )

    # Analyze login patterns
    for login in logins:
        analyze_login_pattern(login["ip"], login["datetime"])

Related Files:
    - app/api/domains/cho.py: Client connection handling
    - app/usecases/achievements.py: Security monitoring
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TypedDict, cast

from sqlalchemy import Column, Date, DateTime, Integer, String, func, insert, select

import app.state.services
from app.repositories import Base


class IngameLoginsTable(Base):
    __tablename__ = "ingame_logins"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    userid = Column("userid", Integer, nullable=False)
    ip = Column("ip", String(45), nullable=False)
    osu_ver = Column("osu_ver", Date, nullable=False)
    osu_stream = Column("osu_stream", String(11), nullable=False)
    datetime = Column("datetime", DateTime, nullable=False)


READ_PARAMS = (
    IngameLoginsTable.id,
    IngameLoginsTable.userid,
    IngameLoginsTable.ip,
    IngameLoginsTable.osu_ver,
    IngameLoginsTable.osu_stream,
    IngameLoginsTable.datetime,
)


class IngameLogin(TypedDict):
    id: int
    userid: str
    ip: str
    osu_ver: date
    osu_stream: str
    datetime: datetime


class InGameLoginUpdateFields(TypedDict, total=False):
    userid: str
    ip: str
    osu_ver: date
    osu_stream: str


async def create(
    user_id: int,
    ip: str,
    osu_ver: date,
    osu_stream: str,
) -> IngameLogin:
    """Create a new login entry in the database."""
    insert_stmt = insert(IngameLoginsTable).values(
        userid=user_id,
        ip=ip,
        osu_ver=osu_ver,
        osu_stream=osu_stream,
        datetime=func.now(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(IngameLoginsTable.id == rec_id)
    ingame_login = await app.state.services.database.fetch_one(select_stmt)

    assert ingame_login is not None
    return cast(IngameLogin, ingame_login)


async def fetch_one(id: int) -> IngameLogin | None:
    """Fetch a login entry from the database."""
    select_stmt = select(*READ_PARAMS).where(IngameLoginsTable.id == id)
    ingame_login = await app.state.services.database.fetch_one(select_stmt)
    return cast(IngameLogin | None, ingame_login)


async def fetch_count(
    user_id: int | None = None,
    ip: str | None = None,
) -> int:
    """Fetch the number of logins in the database."""
    select_stmt = select(func.count().label("count")).select_from(IngameLoginsTable)
    if user_id is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.userid == user_id)
    if ip is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.ip == ip)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    user_id: int | None = None,
    ip: str | None = None,
    osu_ver: date | None = None,
    osu_stream: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[IngameLogin]:
    """Fetch a list of logins from the database."""
    select_stmt = select(*READ_PARAMS)

    if user_id is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.userid == user_id)
    if ip is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.ip == ip)
    if osu_ver is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.osu_ver == osu_ver)
    if osu_stream is not None:
        select_stmt = select_stmt.where(IngameLoginsTable.osu_stream == osu_stream)

    if page is not None and page_size is not None:
        select_stmt.limit(page_size).offset((page - 1) * page_size)

    ingame_logins = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[IngameLogin], ingame_logins)
