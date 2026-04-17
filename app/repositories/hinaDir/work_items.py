from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict, cast

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.dialects.mysql import TINYINT as TinyInt

import app.state.services
from app.repositories import Base


class BeatmapWorkItemTable(Base):
    __tablename__ = "beatmap_work_items"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    set_id = Column("set_id", Integer, nullable=False)
    request_id = Column("request_id", Integer, nullable=True)
    review_state = Column("review_state", String(16), nullable=False, server_default="pending")
    assigned_to = Column("assigned_to", Integer, nullable=True)
    assigned_at = Column("assigned_at", DateTime, nullable=True)
    created_at = Column("created_at", DateTime, nullable=False, server_default=func.now())
    updated_at = Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    resolved_at = Column("resolved_at", DateTime, nullable=True)
    resolution = Column("resolution", String(32), nullable=True)
    checklist = Column("checklist", JSON, nullable=True)
    priority = Column("priority", TinyInt, nullable=False, server_default="0")

    __table_args__ = (
        Index("idx_bwi_set_id", "set_id"),
        Index("idx_bwi_review_state", "review_state"),
        Index("idx_bwi_assigned", "assigned_to"),
        Index("idx_bwi_created", "created_at"),
        Index("idx_bwi_state_priority", "review_state", "priority", "created_at"),
    )


READ_PARAMS = (
    BeatmapWorkItemTable.id,
    BeatmapWorkItemTable.set_id,
    BeatmapWorkItemTable.request_id,
    BeatmapWorkItemTable.review_state,
    BeatmapWorkItemTable.assigned_to,
    BeatmapWorkItemTable.assigned_at,
    BeatmapWorkItemTable.created_at,
    BeatmapWorkItemTable.updated_at,
    BeatmapWorkItemTable.resolved_at,
    BeatmapWorkItemTable.resolution,
    BeatmapWorkItemTable.checklist,
    BeatmapWorkItemTable.priority,
)


class BeatmapWorkItem(TypedDict):
    id: int
    set_id: int
    request_id: int | None
    review_state: str
    assigned_to: int | None
    assigned_at: datetime | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolution: str | None
    checklist: dict[str, Any] | None
    priority: int


async def create(
    set_id: int,
    request_id: int | None = None,
    checklist: dict | None = None,
    priority: int = 0,
) -> BeatmapWorkItem:
    """Create a new beatmap work item."""
    insert_stmt = insert(BeatmapWorkItemTable).values(
        set_id=set_id,
        request_id=request_id,
        checklist=checklist,
        priority=priority,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)
    if rec_id is None:
        raise RuntimeError("Failed to insert work item record")

    select_stmt = select(*READ_PARAMS).where(BeatmapWorkItemTable.id == rec_id)
    item = await app.state.services.database.fetch_one(select_stmt)
    if item is None:
        raise RuntimeError("Failed to fetch inserted work item record")
    return cast(BeatmapWorkItem, item)


async def fetch_one(id: int) -> BeatmapWorkItem | None:
    """Fetch a single work item by ID."""
    select_stmt = select(*READ_PARAMS).where(BeatmapWorkItemTable.id == id)
    item = await app.state.services.database.fetch_one(select_stmt)
    return cast(BeatmapWorkItem, item) if item else None


async def fetch_queue(
    review_state: str | None = None,
    assigned_to: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[BeatmapWorkItem]:
    """Fetch the review queue with optional filters."""
    select_stmt = select(*READ_PARAMS)
    if review_state is not None:
        select_stmt = select_stmt.where(
            BeatmapWorkItemTable.review_state == review_state,
        )
    if assigned_to is not None:
        select_stmt = select_stmt.where(
            BeatmapWorkItemTable.assigned_to == assigned_to,
        )
    select_stmt = (
        select_stmt
        .order_by(
            BeatmapWorkItemTable.priority.desc(),
            BeatmapWorkItemTable.created_at.asc(),
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[BeatmapWorkItem], rows)


async def partial_update(id: int, **kwargs: Any) -> BeatmapWorkItem | None:
    """Update specific fields of a work item."""
    update_stmt = (
        update(BeatmapWorkItemTable)
        .where(BeatmapWorkItemTable.id == id)
        .values(**kwargs)
    )
    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(BeatmapWorkItemTable.id == id)
    item = await app.state.services.database.fetch_one(select_stmt)
    return cast(BeatmapWorkItem, item) if item else None
