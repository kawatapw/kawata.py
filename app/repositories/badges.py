"""
Badges Repository - Database Operations for Badge Management

This module provides database operations for managing badges and badge styles
in the osu! server application. It implements the repository pattern for badge
data access, providing a clean abstraction layer between the application logic
and database operations for badge storage, retrieval, and management.

The repository handles all CRUD operations for badges, including creation,
retrieval, updating, and deletion of badge records. It also manages badge
styles that define the visual appearance of badges on player profiles.

Key Features:
    - Complete CRUD operations for badge data
    - Badge style management for visual customization
    - Type-safe data access with TypedDict definitions
    - Support for pagination and filtering
    - Integration with badge style system
    - Database connection management through app state

Integration Points:
    - Badge display in app/api/v2/players.py
    - Badge assignment in app/api/v2/players.py
    - Badge styling in app/objects/badge_style.py
    - Database connection in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - badges table: id, name, description, priority
    - badge_styles table: id, badge_id, type, value
    - Foreign key relationship between badges and badge_styles

Badge Structure:
    - id: Unique identifier for the badge
    - name: Display name of the badge
    - description: Description of what the badge represents
    - priority: Display priority (higher values shown first)
    - badge_styles: List of style configurations for visual appearance

Badge Style Types:
    - color: Text or element color values
    - border: Border styling properties
    - background: Background color or image properties
    - font: Font family and styling properties
    - size: Dimension and sizing properties

Usage Pattern:
    # Create a new badge
    badge = await create(
        name="First Place",
        description="Awarded for achieving first place",
        priority=10
    )

    # Fetch badge by ID or name
    badge = await fetch_one(id=1)
    badge = await fetch_one(name="First Place")

    # Fetch badge styles
    styles = await fetch_styles(badge_id=1)

    # Update badge
    updated = await update(
        id=1,
        description="Updated description"
    )

    # Delete badge
    deleted = await delete(id=1)

Related Files:
    - app/objects/badge.py: Badge data model
    - app/objects/badge_style.py: Badge style data model
    - app/api/v2/players.py: Player profile display with badges
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

import textwrap
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel

READ_PARAMS = textwrap.dedent(
    """\
        id, name, description, priority
    """,
)


class BadgeStyle(TypedDict):
    id: int
    badge_id: int
    type: str
    value: str


class Badge(TypedDict):
    id: int
    name: str
    description: str
    priority: int
    badge_styles: list[BadgeStyle]


class BadgeUpdateFields(TypedDict, total=False):
    name: str
    description: str
    priority: int
    badge_styles: list[BadgeStyle]


async def create(
    name: str,
    description: str,
    priority: int,
) -> Badge:
    """Create a new badge in the database."""
    query = """\
        INSERT INTO badges (name, description, priority)
             VALUES (:name, :description, :priority)
    """
    params: dict[str, Any] = {
        "name": name,
        "description": description,
        "priority": priority,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = rf"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = :id
    """  # nosec B608
    params = {
        "id": rec_id,
    }
    badge: dict[str, Any] | None = await app.state.services.database.fetch_one(
        query,
        params,
    )

    if badge is None:
        raise ValueError(f"Badge with id {rec_id} not found after creation")
    return cast("Badge", badge)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    description: str | None = None,
    priority: int | None = None,
) -> Badge | None:
    """Fetch a single badge from the database."""
    if id is None and name is None and description is None and priority is None:
        raise ValueError("Must provide at least one parameter.")

    query = rf"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = COALESCE(:id, id)
           AND name = COALESCE(:name, name)
           AND description = COALESCE(:description, description)
           AND priority = COALESCE(:priority, priority)
    """  # nosec B608
    params: dict[str, Any] = {
        "id": id,
        "name": name,
        "description": description,
        "priority": priority,
    }
    badge: dict[str, Any] | None = await app.state.services.database.fetch_one(
        query,
        params,
    )

    return cast("Badge", badge) if badge is not None else None


async def fetch_styles(badge_id: int) -> list[BadgeStyle]:
    """Fetch the styles of a badge from the database."""
    query = """\
        SELECT id, badge_id, type, value
          FROM badge_styles
         WHERE badge_id = :badge_id
    """
    params: dict[str, Any] = {
        "badge_id": badge_id,
    }
    styles: list[dict[str, Any]] | None = await app.state.services.database.fetch_all(
        query,
        params,
    )
    return cast("list[BadgeStyle]", styles) if styles is not None else []


async def fetch_count() -> int:
    """Fetch the number of badges in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM badges
    """
    rec: dict[str, Any] | None = await app.state.services.database.fetch_one(query)
    if rec is None:
        raise ValueError("Failed to fetch badge count")
    return cast("int", rec["count"])


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Badge]:
    """Fetch many badges from the database."""
    query = rf"""\
        SELECT {READ_PARAMS}
          FROM badges
    """  # nosec B608
    params: dict[str, Any] = {}

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    badges: list[dict[str, Any]] | None = await app.state.services.database.fetch_all(
        query,
        params,
    )
    return cast("list[Badge]", badges) if badges is not None else []


async def update(
    id: int,
    name: str | _UnsetSentinel = UNSET,
    description: str | _UnsetSentinel = UNSET,
    priority: int | _UnsetSentinel = UNSET,
) -> Badge | None:
    """Update a badge in the database."""
    update_fields: BadgeUpdateFields = {}
    if not isinstance(name, _UnsetSentinel):
        update_fields["name"] = name
    if not isinstance(description, _UnsetSentinel):
        update_fields["description"] = description
    if not isinstance(priority, _UnsetSentinel):
        update_fields["priority"] = priority

    query = rf"""\
        UPDATE badges
           SET {",".join(f"{k} = :{k}" for k in update_fields)}
         WHERE id = :id
    """  # nosec B608
    values = {"id": id} | update_fields
    await app.state.services.database.execute(query, values)

    query = rf"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = :id
    """  # nosec B608
    params: dict[str, Any] = {
        "id": id,
    }
    badge: dict[str, Any] | None = await app.state.services.database.fetch_one(
        query,
        params,
    )
    return cast("Badge", badge) if badge is not None else None


async def delete(id: int) -> Badge | None:
    """Delete a badge from the database."""
    query = rf"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = :id
    """  # nosec B608
    params: dict[str, Any] = {
        "id": id,
    }
    rec: dict[str, Any] | None = await app.state.services.database.fetch_one(
        query,
        params,
    )
    if rec is None:
        return None

    query = """\
        DELETE FROM badges
         WHERE id = :id
    """
    params = {"id": id}
    await app.state.services.database.execute(query, params)
    return cast("Badge", rec)
