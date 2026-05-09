from __future__ import annotations

from datetime import datetime
from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app.repositories import Base


class BeatmapReviewCommentTable(Base):
    __tablename__ = "beatmap_review_comments"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    work_item_id = Column("work_item_id", Integer, nullable=False)
    user_id = Column("user_id", Integer, nullable=False)
    body = Column("body", Text, nullable=False)
    created_at = Column(
        "created_at", DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_brc_work_item", "work_item_id"),
        Index("idx_brc_user", "user_id"),
    )


READ_PARAMS = (
    BeatmapReviewCommentTable.id,
    BeatmapReviewCommentTable.work_item_id,
    BeatmapReviewCommentTable.user_id,
    BeatmapReviewCommentTable.body,
    BeatmapReviewCommentTable.created_at,
)


class BeatmapReviewComment(TypedDict):
    id: int
    work_item_id: int
    user_id: int
    body: str
    created_at: datetime


async def create(
    work_item_id: int,
    user_id: int,
    body: str,
) -> BeatmapReviewComment:
    """Create a new review comment."""
    insert_stmt = insert(BeatmapReviewCommentTable).values(
        work_item_id=work_item_id,
        user_id=user_id,
        body=body,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)
    if rec_id is None:
        raise RuntimeError("Failed to insert review comment record")

    select_stmt = select(*READ_PARAMS).where(BeatmapReviewCommentTable.id == rec_id)
    comment = await app.state.services.database.fetch_one(select_stmt)
    if comment is None:
        raise RuntimeError("Failed to fetch inserted review comment record")
    return cast("BeatmapReviewComment", comment)


async def fetch_by_work_item(
    work_item_id: int,
) -> list[BeatmapReviewComment]:
    """Fetch all comments for a work item, oldest first."""
    select_stmt = (
        select(*READ_PARAMS)
        .where(BeatmapReviewCommentTable.work_item_id == work_item_id)
        .order_by(BeatmapReviewCommentTable.created_at.asc())
    )
    rows = await app.state.services.database.fetch_all(select_stmt)
    return cast("list[BeatmapReviewComment]", rows)
