"""
Client Hashes Repository - Database Operations for Anti-Cheat Hardware Tracking

This module provides database operations for tracking client hardware hashes
in the osu! server application. It implements the repository pattern for client
hash data access, providing a clean abstraction layer between the application
logic and database operations for hardware fingerprint storage and retrieval.

The repository handles operations for storing and querying client hardware
information used for anti-cheat detection and multi-account identification.
It tracks various hardware identifiers including osu! installation path,
network adapters, uninstall IDs, and disk serial numbers.

Key Features:
    - Hardware fingerprint storage and tracking
    - Multi-account detection through hardware matching
    - Upsert operations for efficient hash updates
    - Occurrence counting for repeated hardware usage
    - Wine/Linux compatibility handling
    - Type-safe data access with TypedDict definitions
    - Integration with user management system

Integration Points:
    - Anti-cheat detection in app/api/domains/cho.py
    - Multi-account detection in app/usecases/achievements.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - userid: User ID (foreign key to users table)
    - osupath: MD5 hash of osu! installation path (32 chars)
    - adapters: MD5 hash of network adapters (32 chars)
    - uninstall_id: MD5 hash of uninstall ID (32 chars)
    - disk_serial: MD5 hash of disk serial number (32 chars)
    - latest_time: Timestamp of last occurrence
    - occurrences: Number of times this hash combination was seen

Hardware Identifiers:
    - osupath: Hash of osu! installation directory path
    - adapters: Hash of network adapter MAC addresses
    - uninstall_id: Hash of Windows uninstall registry entry
    - disk_serial: Hash of disk serial number
    - All identifiers are MD5 hashed for privacy

Anti-Cheat Features:
    - Multi-account detection through hardware matching
    - Wine/Linux compatibility (different detection logic)
    - Occurrence tracking for suspicious patterns
    - Integration with user privilege system

Usage Pattern:
    # Create or update client hash
    client_hash = await create(
        userid=12345,
        osupath="abc123...",
        adapters="def456...",
        uninstall_id="ghi789...",
        disk_serial="jkl012..."
    )

    # Check for hardware matches (multi-account detection)
    matches = await fetch_any_hardware_matches_for_user(
        userid=12345,
        running_under_wine=False,
        adapters="def456...",
        uninstall_id="ghi789...",
        disk_serial="jkl012..."
    )

    # Process matches for anti-cheat
    for match in matches:
        if match["priv"] & Privileges.UNRESTRICTED:
            flag_for_review(match["userid"])

Related Files:
    - app/api/domains/cho.py: Client connection with hash validation
    - app/usecases/achievements.py: Achievement validation with hash checks
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict, cast

from sqlalchemy import CHAR, Column, DateTime, Integer, func, or_, select
from sqlalchemy.dialects.mysql import Insert as MysqlInsert
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.sql import ColumnElement
from sqlalchemy.types import Boolean

import app.state.services
from app.repositories import Base
from app.repositories.users import UsersTable


class ClientHashesTable(Base):
    __tablename__ = "client_hashes"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    osupath = Column("osupath", CHAR(32), nullable=False, primary_key=True)
    adapters = Column("adapters", CHAR(32), nullable=False, primary_key=True)
    uninstall_id = Column("uninstall_id", CHAR(32), nullable=False, primary_key=True)
    disk_serial = Column("disk_serial", CHAR(32), nullable=False, primary_key=True)
    latest_time = Column("latest_time", DateTime, nullable=False)
    occurrences = Column("occurrences", Integer, nullable=False, server_default="0")


READ_PARAMS = (
    ClientHashesTable.userid,
    ClientHashesTable.osupath,
    ClientHashesTable.adapters,
    ClientHashesTable.uninstall_id,
    ClientHashesTable.disk_serial,
    ClientHashesTable.latest_time,
    ClientHashesTable.occurrences,
)


class ClientHash(TypedDict):
    userid: int
    osupath: str
    adapters: str
    uninstall_id: str
    disk_serial: str
    latest_time: datetime
    occurrences: int


class ClientHashWithPlayer(ClientHash):
    name: str
    priv: int


async def create(
    userid: int,
    osupath: str,
    adapters: str,
    uninstall_id: str,
    disk_serial: str,
) -> ClientHash:
    """Create a new client hash entry in the database."""
    insert_stmt: MysqlInsert = (
        mysql_insert(ClientHashesTable)
        .values(
            userid=userid,
            osupath=osupath,
            adapters=adapters,
            uninstall_id=uninstall_id,
            disk_serial=disk_serial,
            latest_time=func.now(),
            occurrences=1,
        )
        .on_duplicate_key_update(
            latest_time=func.now(),
            occurrences=ClientHashesTable.occurrences + 1,
        )
    )

    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(ClientHashesTable.userid == userid)
        .where(ClientHashesTable.osupath == osupath)
        .where(ClientHashesTable.adapters == adapters)
        .where(ClientHashesTable.uninstall_id == uninstall_id)
        .where(ClientHashesTable.disk_serial == disk_serial)
    )
    client_hash = await app.state.services.database.fetch_one(select_stmt)

    assert client_hash is not None
    return cast(ClientHash, client_hash)


async def fetch_any_hardware_matches_for_user(
    userid: int,
    running_under_wine: bool,
    adapters: str,
    uninstall_id: str,
    disk_serial: str | None = None,
) -> list[ClientHashWithPlayer]:
    """\
    Fetch a list of matching hardware addresses where any of
    `adapters`, `uninstall_id` or `disk_serial` match other users
    from the database.
    """
    select_stmt = (
        select(*READ_PARAMS, UsersTable.name, UsersTable.priv)
        .join(UsersTable, ClientHashesTable.userid == UsersTable.id)
        .where(ClientHashesTable.userid != userid)
    )

    if running_under_wine:
        select_stmt = select_stmt.where(ClientHashesTable.uninstall_id == uninstall_id)
    else:
        # make disk serial optional in the OR
        oneof_filters: list[ColumnElement[Boolean]] = []
        oneof_filters.append(ClientHashesTable.adapters == adapters)
        oneof_filters.append(ClientHashesTable.uninstall_id == uninstall_id)
        if disk_serial is not None:
            oneof_filters.append(ClientHashesTable.disk_serial == disk_serial)
        select_stmt = select_stmt.where(or_(*oneof_filters))

    client_hashes = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[ClientHashWithPlayer], client_hashes)
