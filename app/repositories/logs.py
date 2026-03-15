"""
Logs Repository - Database Operations for Administrative Action Logging

This module provides database operations for logging administrative actions
in the osu! server application. It implements the repository pattern for log
data access, providing a clean abstraction layer between the application logic
and database operations for action logging and audit trail management.

The repository handles operations for storing administrative actions performed
by moderators and administrators, including user restrictions, silences, and
other moderation activities. Each log entry includes information about who
performed the action, who was affected, and the reason for the action.

Key Features:
    - Administrative action logging with unique hash identification
    - Moderator and administrator action tracking
    - Target user identification for affected players
    - Action type categorization (restrict, silence, etc.)
    - Reason storage for audit trail purposes
    - Timestamp tracking for action timing
    - Type-safe data access with TypedDict definitions

Integration Points:
    - Administrative actions in app/objects/player.py
    - Moderation tools in app/api/v2/players.py
    - Audit logging in app/usecases/achievements.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - id: SHA256 hash of log content (primary key)
    - mod: User ID of the moderator/administrator who performed the action
    - target: User ID of the player who was affected by the action
    - action: Type of action performed (restrict, silence, unrestrict, etc.)
    - reason: Reason for the action (max 2048 characters)
    - time: Timestamp when the action was performed
    - type: Additional type information for the action

Log Entry Structure:
    - id: Unique hash identifier for the log entry
    - _from: Moderator/administrator who performed the action
    - to: Player who was affected by the action
    - action: Type of action performed
    - msg: Reason for the action
    - time: When the action was performed
    - type: Additional type information

Action Types:
    - restrict: Player was restricted from the server
    - unrestrict: Player was unrestricted
    - silence: Player was silenced for a duration
    - unsilence: Player was unsilenced
    - Other administrative actions as needed

Usage Pattern:
    # Log a restriction action
    log = await create(
        _from=admin_id,
        to=player_id,
        action="restrict",
        msg="Cheating detected"
    )
    
    # Log a silence action
    log = await create(
        _from=moderator_id,
        to=player_id,
        action="silence",
        msg="Inappropriate language",
        type=1
    )
    
    # Process log entries for audit
    log_hash = log["id"]
    moderator = log["_from"]
    target = log["to"]
    action = log["action"]
    reason = log["msg"]

Related Files:
    - app/objects/player.py: Player administrative actions
    - app/api/v2/players.py: Moderation API endpoints
    - app/usecases/achievements.py: Achievement validation with logging
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


from sqlalchemy import SmallInteger as TinyInt
from sqlalchemy import Text

class LogTable(Base):
    __tablename__ = "logs"

    id = Column("id", Text, nullable=False, primary_key=True)
    mod = Column("mod", Integer, nullable=False)
    target = Column("target", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    reason = Column("reason", String(2048, collation="utf8"), nullable=True)
    time = Column("time", DateTime, nullable=False, onupdate=func.now())
    type = Column("type", TinyInt, nullable=False, default=False)

READ_PARAMS = (
    LogTable.id,
    LogTable.mod.label("from"),
    LogTable.target.label("to"),
    LogTable.action,
    LogTable.reason.label("msg"),
    LogTable.time,
    LogTable.type,
)

class Log(TypedDict):
    id: str
    _from: int
    to: int
    action: str
    msg: str | None
    time: datetime
    type: bool

import hashlib

async def create(
    _from: int,
    to: int,
    action: str,
    msg: str,
    type: int = 0,
) -> Log:
    """Create a new log entry in the database."""
    
    # Generate a unique hash for the log entry
    log_content = f"{_from}{to}{action}{msg}{type}"
    log_hash = hashlib.sha256(log_content.encode()).hexdigest()

    insert_stmt = insert(LogTable).values(
        {
            "id": log_hash,
            "mod": _from,
            "target": to,
            "action": action,
            "reason": msg,
            "time": func.now(),
            "type": type,
        },
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(LogTable.id == log_hash)
    log = await app.state.services.database.fetch_one(select_stmt)
    assert log is not None
    return cast(Log, log)