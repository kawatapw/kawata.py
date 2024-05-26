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