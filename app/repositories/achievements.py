"""
Achievements Repository - Database Operations for Achievement Management

This module provides database operations for managing achievements in the osu!
server application. It implements the repository pattern for achievement data
access, providing a clean abstraction layer between the application logic and
database operations for achievement storage, retrieval, and management.

The repository handles all CRUD operations for achievements, including creation,
retrieval, updating, and deletion of achievement records. It uses SQLAlchemy for
database interactions and provides both individual and batch operations for
efficient data management.

Key Features:
    - Complete CRUD operations for achievement data
    - SQLAlchemy-based database interactions
    - Type-safe data access with TypedDict definitions
    - Support for pagination and filtering
    - Dynamic condition evaluation for achievement unlocking
    - Unique constraint enforcement for achievement properties
    - Integration with the application state management system

Integration Points:
    - Achievement validation in app/usecases/achievements.py
    - Score processing in app/objects/score.py
    - Player achievement tracking in app/repositories/user_achievements.py
    - Database connection management in app/state/services.py
    - Application state in app/state/__init__.py

Database Schema:
    - id: Primary key with auto-increment
    - file: Achievement asset filename (unique)
    - name: Achievement display name (unique)
    - desc: Achievement description (unique)
    - cond: Condition string for achievement unlocking

Achievement Conditions:
    - Conditions are stored as strings in the database
    - They are evaluated as lambda functions at runtime
    - Format: lambda score, mode_vn: <condition_expression>
    - Examples: "score.passed", "score.acc >= 95.0", "score.max_combo >= 1000"

Usage Pattern:
    # Create a new achievement
    achievement = await create(
        file="pass_map",
        name="First Pass",
        desc="Pass your first map",
        cond="score.passed"
    )

    # Fetch achievement by ID or name
    achievement = await fetch_one(id=1)
    achievement = await fetch_one(name="First Pass")

    # Fetch all achievements with pagination
    achievements = await fetch_many(page=1, page_size=10)

    # Update achievement
    updated = await partial_update(
        id=1,
        desc="Updated description"
    )

    # Delete achievement
    deleted = await delete_one(id=1)

Related Files:
    - app/usecases/achievements.py: Achievement validation logic
    - app/objects/achievement.py: Achievement data model
    - app/repositories/user_achievements.py: Player achievement tracking
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypedDict, cast

import app.state.services
from app._typing import UNSET, _UnsetSentinel
from app.repositories import Base

if TYPE_CHECKING:
    from app.objects.score import Score


from sqlalchemy import (
    Column,
    Index,
    Integer,
    String,
    delete,
    func,
    insert,
    select,
    update,
)

# Safe expression evaluator for achievement conditions.
# Replaces eval() to prevent arbitrary code execution from DB content.

_SAFE_COMPARE_OPS: dict[type, Callable[..., bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_SAFE_BOOL_OPS: dict[type, Callable[..., bool]] = {
    ast.And: lambda vals: all(vals),
    ast.Or: lambda vals: any(vals),
}

_SAFE_UNARY_OPS: dict[type, Callable[..., Any]] = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
}

_SAFE_BIN_OPS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
}


def _safe_eval_node(
    node: ast.AST,
    score: Score,
    mode_vn: int,
) -> Any:
    """Recursively evaluate an AST node with restricted operations."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, score, mode_vn)

    # Numeric, string, and boolean literals
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, str, bool)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value)}")

    # Variable names: only 'score', 'mode_vn', 'True', 'False'
    if isinstance(node, ast.Name):
        if node.id == "score":
            return score
        if node.id == "mode_vn":
            return mode_vn
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        raise ValueError(f"Unsupported variable: {node.id!r}")

    # Attribute access: only on 'score' (e.g., score.acc, score.pp)
    if isinstance(node, ast.Attribute):
        obj = _safe_eval_node(node.value, score, mode_vn)
        if obj is not score:
            raise ValueError("Attribute access only allowed on 'score'")
        if not isinstance(node.attr, str) or node.attr.startswith("_"):
            raise ValueError(f"Unsafe attribute: {node.attr!r}")
        return getattr(score, node.attr)

    # Comparison operators: ==, !=, <, <=, >, >=
    if isinstance(node, ast.Compare):
        left = _safe_eval_node(node.left, score, mode_vn)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            op_func = _SAFE_COMPARE_OPS.get(type(op))
            if op_func is None:
                raise ValueError(f"Unsupported comparison: {type(op).__name__}")
            right = _safe_eval_node(comparator, score, mode_vn)
            if not op_func(left, right):
                return False
            left = right
        return True

    # Boolean operators: and, or
    if isinstance(node, ast.BoolOp):
        op_func = _SAFE_BOOL_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported boolean op: {type(node.op).__name__}")
        values = [_safe_eval_node(v, score, mode_vn) for v in node.values]
        return op_func(values)

    # Unary operators: not, - (negation)
    if isinstance(node, ast.UnaryOp):
        op_func = _SAFE_UNARY_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary op: {type(node.op).__name__}")
        return op_func(_safe_eval_node(node.operand, score, mode_vn))

    # Binary operators: +, -, * (for arithmetic in conditions)
    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BIN_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported binary op: {type(node.op).__name__}")
        left = _safe_eval_node(node.left, score, mode_vn)
        right = _safe_eval_node(node.right, score, mode_vn)
        return op_func(left, right)

    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


_ALLOWED_AST_TYPES: frozenset[type] = frozenset({
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.Attribute,
    ast.Compare,
    ast.BoolOp,
    ast.UnaryOp,
    ast.BinOp,
    ast.Load,
    # Comparison operator nodes
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    # Boolean operator nodes
    ast.And, ast.Or,
    # Unary operator nodes
    ast.Not, ast.USub,
    # Binary operator nodes
    ast.Add, ast.Sub, ast.Mult, ast.BitAnd, ast.BitOr,
})


def _make_achievement_cond(cond_str: str) -> Callable[[Score, int], bool]:
    """Parse an achievement condition string into a safe callable.

    Only allows: attribute access on 'score', comparisons, boolean
    operators (and/or/not), arithmetic (+/-/*/&/|), and literals.
    """
    try:
        tree = ast.parse(cond_str, mode="eval")
    except SyntaxError as exc:
        raise ValueError(
            f"Invalid achievement condition syntax: {cond_str!r}",
        ) from exc

    # Eagerly validate the AST: reject any node types not handled
    # by _safe_eval_node so bad conditions fail at load time.
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_AST_TYPES:
            raise ValueError(
                f"Unsupported AST node {type(node).__name__!r} "
                f"in achievement condition: {cond_str!r}",
            )

    def evaluator(score: Score, mode_vn: int) -> bool:
        return _safe_eval_node(tree, score, mode_vn)

    return evaluator

class AchievementsTable(Base):
    __tablename__ = "achievements"

    id = Column("id", Integer, primary_key=True, nullable=False, autoincrement=True)
    file = Column("file", String(128), nullable=False)
    name = Column("name", String(128, collation="utf8"), nullable=False)
    desc = Column("desc", String(256, collation="utf8"), nullable=False)
    cond = Column("cond", String(64), nullable=False)

    __table_args__ = (
        Index("achievements_desc_uindex", desc, unique=True),
        Index("achievements_file_uindex", file, unique=True),
        Index("achievements_name_uindex", name, unique=True),
    )


READ_PARAMS = (
    AchievementsTable.id,
    AchievementsTable.file,
    AchievementsTable.name,
    AchievementsTable.desc,
    AchievementsTable.cond,
)


class Achievement(TypedDict):
    id: int
    file: str
    name: str
    desc: str
    cond: Callable[[Score, int], bool]


async def create(
    file: str,
    name: str,
    desc: str,
    cond: str,
) -> Achievement:
    """Create a new achievement."""
    # Validate condition before persisting to DB
    cond_func = _make_achievement_cond(cond)

    insert_stmt = insert(AchievementsTable).values(
        file=file,
        name=name,
        desc=desc,
        cond=cond,
    )
    rec_id = await app.state.services.database.execute(insert_stmt)

    select_stmt = select(*READ_PARAMS).where(AchievementsTable.id == rec_id)
    achievement = await app.state.services.database.fetch_one(select_stmt)
    assert achievement is not None

    achievement["cond"] = cond_func
    return cast(Achievement, achievement)


async def fetch_one(
    id: int | None = None,
    name: str | None = None,
) -> Achievement | None:
    """Fetch a single achievement."""
    if id is None and name is None:
        raise ValueError("Must provide at least one parameter.")

    select_stmt = select(*READ_PARAMS)

    if id is not None:
        select_stmt = select_stmt.where(AchievementsTable.id == id)
    if name is not None:
        select_stmt = select_stmt.where(AchievementsTable.name == name)

    achievement = await app.state.services.database.fetch_one(select_stmt)
    if achievement is None:
        return None

    achievement["cond"] = _make_achievement_cond(achievement["cond"])
    return cast(Achievement, achievement)


async def fetch_count() -> int:
    """Fetch the number of achievements."""
    select_stmt = select(func.count().label("count")).select_from(AchievementsTable)

    rec = await app.state.services.database.fetch_one(select_stmt)
    assert rec is not None
    return cast(int, rec["count"])


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Achievement]:
    """Fetch a list of achievements."""
    select_stmt = select(*READ_PARAMS)
    if page is not None and page_size is not None:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    achievements: (
        list[dict[str, Any]] | None
    ) = await app.state.services.database.fetch_all(select_stmt)
    if achievements is not None:
        for achievement in achievements:
            achievement["cond"] = _make_achievement_cond(achievement["cond"])
    else:
        achievements = []

    return cast(list[Achievement], achievements)


async def partial_update(
    id: int,
    file: str | _UnsetSentinel = UNSET,
    name: str | _UnsetSentinel = UNSET,
    desc: str | _UnsetSentinel = UNSET,
    cond: str | _UnsetSentinel = UNSET,
) -> Achievement | None:
    """Update an existing achievement."""
    # Validate condition before persisting to DB
    if not isinstance(cond, _UnsetSentinel):
        _make_achievement_cond(cond)

    update_stmt = update(AchievementsTable).where(AchievementsTable.id == id)
    if not isinstance(file, _UnsetSentinel):
        update_stmt = update_stmt.values(file=file)
    if not isinstance(name, _UnsetSentinel):
        update_stmt = update_stmt.values(name=name)
    if not isinstance(desc, _UnsetSentinel):
        update_stmt = update_stmt.values(desc=desc)
    if not isinstance(cond, _UnsetSentinel):
        update_stmt = update_stmt.values(cond=cond)

    await app.state.services.database.execute(update_stmt)

    select_stmt = select(*READ_PARAMS).where(AchievementsTable.id == id)
    achievement = await app.state.services.database.fetch_one(select_stmt)
    if achievement is None:
        return None

    achievement["cond"] = _make_achievement_cond(achievement["cond"])
    return cast(Achievement, achievement)


async def delete_one(
    id: int,
) -> Achievement | None:
    """Delete an existing achievement."""
    select_stmt = select(*READ_PARAMS).where(AchievementsTable.id == id)
    achievement = await app.state.services.database.fetch_one(select_stmt)
    if achievement is None:
        return None

    delete_stmt = delete(AchievementsTable).where(AchievementsTable.id == id)
    await app.state.services.database.execute(delete_stmt)

    return cast(Achievement, achievement)
