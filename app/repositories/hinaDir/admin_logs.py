from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app.repositories import Base


class AdminV2LogTable(Base):
    __tablename__ = "admin_v2_logs"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    from_id = Column("from_id", Integer, nullable=False)
    to_id = Column("to_id", Integer, nullable=False)
    action = Column("action", String(32), nullable=False)
    msg = Column("msg", String(2048, collation="utf8"), nullable=True)
    created_at = Column(
        "created_at", DateTime, nullable=False, server_default=func.now()
    )
    action_type = Column("action_type", TINYINT, nullable=False, server_default="0")

    __table_args__ = (
        Index("idx_av2logs_action", "action"),
        Index("idx_av2logs_to_id", "to_id"),
        Index("idx_av2logs_from_id", "from_id"),
        Index("idx_av2logs_created", "created_at"),
        Index("idx_av2logs_type_created", "action_type", "created_at"),
    )


READ_PARAMS = (
    AdminV2LogTable.id,
    AdminV2LogTable.from_id,
    AdminV2LogTable.to_id,
    AdminV2LogTable.action,
    AdminV2LogTable.msg,
    AdminV2LogTable.created_at,
    AdminV2LogTable.action_type,
)


class AdminV2Log(TypedDict):
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
    msg: str | None = None,
    action_type: int = 0,
) -> AdminV2Log:
    """Create a new admin V2 log entry."""
    insert_stmt = insert(AdminV2LogTable).values(
        from_id=from_id,
        to_id=to_id,
        action=action,
        msg=msg,
        action_type=action_type,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)
    if rec_id is None:
        raise RuntimeError("Failed to insert admin log record")

    select_stmt = select(*READ_PARAMS).where(AdminV2LogTable.id == rec_id)
    log = await app.state.services.database.fetch_one(select_stmt)
    if log is None:
        raise RuntimeError("Failed to fetch inserted admin log record")
    return cast("AdminV2Log", log)


async def fetch_by_target(
    to_id: int,
    limit: int = 50,
) -> list[AdminV2Log]:
    """Fetch logs for a specific target ordered by most recent."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(AdminV2LogTable.to_id == to_id)
        .order_by(AdminV2LogTable.created_at.desc())
        .limit(limit)
    )
    rows = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[AdminV2Log]", rows)


async def fetch_recent_by_actions(
    actions: list[str],
    limit: int = 10,
) -> list[AdminV2Log]:
    """Fetch recent logs filtered by action names (for dashboard feed)."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(AdminV2LogTable.action.in_(actions))
        .order_by(AdminV2LogTable.created_at.desc())
        .limit(limit)
    )
    rows = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[AdminV2Log]", rows)


async def fetch_by_targets_and_type(
    target_ids: list[int],
    action_type: int,
    limit: int = 20,
) -> list[AdminV2Log]:
    """Fetch logs for multiple targets of a specific type (for beatmap history)."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(
            AdminV2LogTable.to_id.in_(target_ids),
            AdminV2LogTable.action_type == action_type,
        )
        .order_by(AdminV2LogTable.created_at.desc())
        .limit(limit)
    )
    rows = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[AdminV2Log]", rows)
