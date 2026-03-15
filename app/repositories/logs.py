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
    - Administrative action logging with auto-increment identification
    - Moderator and administrator action tracking
    - Target user identification for affected players
    - Action type categorization (restrict, silence, etc.)
    - Message storage for audit trail purposes
    - Timestamp tracking for action timing
    - Type-safe data access with TypedDict definitions

Integration Points:
    - Administrative actions in app/objects/player.py
    - Moderation tools in app/api/v2/players.py
    - Audit logging in app/usecases/achievements.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - id: Auto-increment integer (primary key)
    - from_id: User ID of the moderator/administrator who performed the action
    - to_id: User ID of the player who was affected by the action
    - action: Type of action performed (restrict, silence, unrestrict, etc.)
    - msg: Message/reason for the action (max 2048 characters)
    - created_at: Timestamp when the action was performed
    - action_type: Type of action (0=user, 1=map, 2=badge)

Log Entry Structure:
    - id: Auto-increment identifier for the log entry
    - from_id: Moderator/administrator who performed the action
    - to_id: Player who was affected by the action
    - action: Type of action performed
    - msg: Reason for the action
    - created_at: When the action was performed
    - action_type: Type of action (0=user, 1=map, 2=badge)

Action Types:
    - restrict: Player was restricted from the server
    - unrestrict: Player was unrestricted
    - silence: Player was silenced for a duration
    - unsilence: Player was unsilenced
    - Other administrative actions as needed

Usage Pattern:
    # Log a restriction action
    log = await create(
        from_id=admin_id,
        to_id=player_id,
        action="restrict",
        msg="Cheating detected"
    )
    
    # Log a silence action
    log = await create(
        from_id=moderator_id,
        to_id=player_id,
        action="silence",
        msg="Inappropriate language",
        action_type=1
    )
    
    # Process log entries for audit
    log_id = log["id"]
    moderator = log["from_id"]
    target = log["to_id"]
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

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    from_id = Column("from_id", Integer, nullable=False)
    to_id = Column("to_id", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    msg = Column("msg", String(2048, collation="utf8"), nullable=True)
    created_at = Column("created_at", DateTime, nullable=False, server_default=func.now())
    action_type = Column("action_type", TinyInt, nullable=False, default=0)

READ_PARAMS = (
    LogTable.id,
    LogTable.from_id,
    LogTable.to_id,
    LogTable.action,
    LogTable.msg,
    LogTable.created_at,
    LogTable.action_type,
)

class Log(TypedDict):
    id: int
    from_id: int
    to_id: int
    action: str
    msg: str | None
    created_at: datetime
    action_type: int

async def create(
    from_id: int,
    to_id: int,
    action: str,
    msg: str,
    action_type: int = 0,
) -> Log:
    """Create a new log entry in the database."""
    
    insert_stmt = insert(LogTable).values(
        {
            "from_id": from_id,
            "to_id": to_id,
            "action": action,
            "msg": msg,
            "created_at": func.now(),
            "action_type": action_type,
        },
    )
    log_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(LogTable.id == log_id)
    log = await app.state.services.database.fetch_one(select_stmt)
    assert log is not None
    return cast(Log, log)