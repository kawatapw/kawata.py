"""
Mail Repository - Database Operations for User Messaging System

This module provides database operations for managing user-to-user messaging
in the osu! server application. It implements the repository pattern for mail
data access, providing a clean abstraction layer between the application logic
and database operations for message storage, retrieval, and management.

The repository handles operations for storing and retrieving private messages
between players, including message creation, inbox management, and read status
tracking. Messages are associated with sender and recipient user IDs and
include timestamps for chronological ordering.

Key Features:
    - Private message creation and storage
    - Inbox management with read/unread status
    - Conversation threading between users
    - Username resolution for display purposes
    - Timestamp tracking for message ordering
    - Type-safe data access with TypedDict definitions
    - Integration with user management system

Integration Points:
    - Messaging system in app/api/domains/cho.py
    - User management in app/repositories/users.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py
    - Packet handling in app/packets.py

Database Schema:
    - id: Primary key with auto-increment
    - from_id: User ID of the message sender
    - to_id: User ID of the message recipient
    - msg: Message content (max 2048 characters)
    - time: Unix timestamp when message was sent
    - read: Boolean flag indicating if message has been read

Message Structure:
    - id: Unique identifier for the message
    - from_id: User who sent the message
    - to_id: User who received the message
    - msg: The actual message content
    - time: When the message was sent (Unix timestamp)
    - read: Whether the message has been read by the recipient

Messaging Features:
    - Private messaging between players
    - Read/unread status tracking
    - Conversation history retrieval
    - Username resolution for display
    - Timestamp-based message ordering

Usage Pattern:
    # Send a new message
    message = await create(
        from_id=sender_id,
        to_id=recipient_id,
        msg="Hello, how are you?"
    )

    # Get all messages for a user
    messages = await fetch_all_mail_to_user(
        user_id=12345,
        read=False  # Only unread messages
    )

    # Mark conversation as read
    await mark_conversation_as_read(
        to_id=recipient_id,
        from_id=sender_id
    )

    # Process messages for display
    for message in messages:
        sender_name = message["from_name"]
        recipient_name = message["to_name"]
        content = message["msg"]
        timestamp = message["time"]

Related Files:
    - app/api/domains/cho.py: Client connection with messaging
    - app/repositories/users.py: User management integration
    - app/packets.py: Packet creation for message delivery
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict, cast

from sqlalchemy import Column, Integer, String, func, insert, select, update
from sqlalchemy.dialects.mysql import TINYINT

import app.state.services
from app.repositories import Base
from app.repositories.users import UsersTable


class MailTable(Base):
    __tablename__ = "mail"

    id = Column("id", Integer, nullable=False, primary_key=True, autoincrement=True)
    from_id = Column("from_id", Integer, nullable=False)
    to_id = Column("to_id", Integer, nullable=False)
    msg = Column("msg", String(2048, collation="utf8"), nullable=False)
    time = Column("time", Integer, nullable=True)
    read = Column("read", TINYINT(1), nullable=False, server_default="0")


READ_PARAMS = (
    MailTable.id,
    MailTable.from_id,
    MailTable.to_id,
    MailTable.msg,
    MailTable.time,
    MailTable.read,
)


class Mail(TypedDict):
    id: int
    from_id: int
    to_id: int
    msg: str
    time: int
    read: bool


class MailWithUsernames(Mail):
    from_name: str
    to_name: str


async def create(from_id: int, to_id: int, msg: str) -> Mail:
    """Create a new mail entry in the database."""
    insert_stmt = insert(MailTable).values(
        from_id=from_id,
        to_id=to_id,
        msg=msg,
        time=func.unix_timestamp(),
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(MailTable.id == rec_id)
    mail = await app.state.services.database.fetch_one(select_stmt)
    assert mail is not None
    return cast(Mail, mail)


async def fetch_all_mail_to_user(
    user_id: int,
    read: bool | None = None,
) -> list[MailWithUsernames]:
    """Fetch all of mail to a given target from the database."""
    from_subquery = select(UsersTable.name).where(UsersTable.id == MailTable.from_id)
    to_subquery = select(UsersTable.name).where(UsersTable.id == MailTable.to_id)

    select_stmt = select(
        *READ_PARAMS,
        from_subquery.label("from_name"),
        to_subquery.label("to_name"),
    ).where(MailTable.to_id == user_id)

    if read is not None:
        select_stmt = select_stmt.where(MailTable.read == read)

    mail = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[MailWithUsernames], mail)


async def mark_conversation_as_read(to_id: int, from_id: int) -> list[Mail]:
    """Mark any mail in a user's conversation with another user as read."""
    select_stmt = select(*READ_PARAMS).where(
        MailTable.to_id == to_id,
        MailTable.from_id == from_id,
        MailTable.read.is_(False),
    )
    mail = await app.state.services.database.fetch_all(select_stmt)
    if not mail:
        return []

    update_stmt = (
        update(MailTable)
        .where(MailTable.to_id == to_id)
        .where(MailTable.from_id == from_id)
        .where(MailTable.read.is_(False))
        .values(read=True)
    )
    await app.state.services.database.execute(update_stmt)
    return cast(list[Mail], mail)
