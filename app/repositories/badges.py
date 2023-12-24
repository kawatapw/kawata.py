from __future__ import annotations

import textwrap
from typing import Any
from typing import cast
from typing import TypedDict

import app.state.services
from app._typing import _UnsetSentinel
from app._typing import UNSET
from kawaweb.gulag.app.objects import badge

READ_PARAMS = textwrap.dedent(
    """\
        id, name, description, priority
    """,
)

class Badge(TypedDict):
    id: int
    name: str
    description: str
    priority: int
    badge_styles: list[badge.Badge_Style]

class BadgeUpdateFields(TypedDict, total=False):
    name: str
    description: str
    priority: int
    badge_styles: list[badge.Badge_Style]
class BadgeStyle(TypedDict):
    id: int
    badge_id: int
    type: str
    value: str


async def create(
    name: str,
    description: str,
    priority: int,
) -> Badge:
    """Create a new badge in the database."""
    query = f"""\
        INSERT INTO badges (name, description, priority)
             VALUES (:name, :description, :priority)
    """
    params: dict[str, Any] = {
        "name": name,
        "description": description,
        "priority": priority,
    }
    rec_id = await app.state.services.database.execute(query, params)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = :id
    """
    params = {
        "id": rec_id,
    }
    badge = await app.state.services.database.fetch_one(query, params)

    assert badge is not None
    return cast(Badge, dict(badge._mapping))

async def fetch_one(
    id: int | None = None,
    name: str | None = None,
    description: str | None = None,
    priority: int | None = None,
) -> Badge | None:
    """Fetch a single badge from the database."""
    if id is None and name is None and description is None and priority is None:
        raise ValueError("Must provide at least one parameter.")

    query = f"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = COALESCE(:id, id)
           AND name = COALESCE(:name, name)
           AND description = COALESCE(:description, description)
           AND priority = COALESCE(:priority, priority)
    """
    params: dict[str, Any] = {"id": id, "name": name, "description": description, "priority": priority}
    badge = await app.state.services.database.fetch_one(query, params)

    return cast(Badge, dict(badge._mapping)) if badge is not None else None

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
    styles = await app.state.services.database.fetch_all(query, params)
    return cast(list[BadgeStyle], [dict(s._mapping) for s in styles])

async def fetch_count() -> int:
    """Fetch the number of badges in the database."""
    query = """\
        SELECT COUNT(*) AS count
          FROM badges
    """
    rec = await app.state.services.database.fetch_one(query)
    assert rec is not None
    return cast(int, rec._mapping["count"])

async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Badge]:
    """Fetch many badges from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM badges
    """
    params: dict[str, Any] = {}

    if page is not None and page_size is not None:
        query += """\
            LIMIT :limit
           OFFSET :offset
        """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size

    badges = await app.state.services.database.fetch_all(query, params)
    return cast(list[Badge], [dict(b._mapping) for b in badges])

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

    query = f"""\
        UPDATE badges
           SET {",".join(f"{k} = :{k}" for k in update_fields)}
         WHERE id = :id
    """
    values = {"id": id} | update_fields
    await app.state.services.database.execute(query, values)

    query = f"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    }
    badge = await app.state.services.database.fetch_one(query, params)
    return cast(Badge, dict(badge._mapping)) if badge is not None else None

async def delete(id: int) -> Badge | None:
    """Delete a badge from the database."""
    query = f"""\
        SELECT {READ_PARAMS}
          FROM badges
         WHERE id = :id
    """
    params: dict[str, Any] = {
        "id": id,
    }
    rec = await app.state.services.database.fetch_one(query, params)
    if rec is None:
        return None

    query = """\
        DELETE FROM badges
         WHERE id = :id
    """
    params = {"id": id}
    await app.state.services.database.execute(query, params)
    return cast(Badge, dict(rec._mapping)) if rec is not None else None