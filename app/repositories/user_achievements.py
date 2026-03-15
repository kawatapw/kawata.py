"""
User Achievements Repository - Database Operations for Player Achievement Tracking

This module provides database operations for tracking player achievements in the
osu! server application. It implements the repository pattern for user achievement
data access, providing a clean abstraction layer between the application logic
and database operations for achievement tracking and management.

The repository handles operations for storing and retrieving which achievements
players have unlocked. It maintains a simple relationship between users and
achievements, allowing the system to track progress and display unlocked
achievements on player profiles.

Key Features:
    - User achievement creation and storage
    - Achievement retrieval by user or achievement ID
    - Pagination support for large achievement lists
    - Type-safe data access with TypedDict definitions
    - Integration with achievement and user management systems
    - Simple many-to-many relationship tracking

Integration Points:
    - Achievement validation in app/usecases/achievements.py
    - Achievement display in app/api/v2/players.py
    - User management in app/repositories/users.py
    - Achievement data in app/repositories/achievements.py
    - Database connection in app/state/services.py

Database Schema:
    - userid: User ID (foreign key to users table)
    - achid: Achievement ID (foreign key to achievements table)
    - Composite primary key (userid, achid)

User Achievement Structure:
    - userid: User who unlocked the achievement
    - achid: Achievement that was unlocked

Achievement Tracking:
    - Simple many-to-many relationship between users and achievements
    - No additional metadata (unlocked timestamp could be added)
    - Efficient lookup by user or achievement
    - Pagination support for displaying achievement lists

Usage Pattern:
    # Record achievement unlock
    user_achievement = await create(
        user_id=12345,
        achievement_id=1
    )
    
    # Get all achievements for a user
    achievements = await fetch_many(user_id=12345)
    
    # Get all users who unlocked an achievement
    users = await fetch_many(achievement_id=1)
    
    # Get achievements with pagination
    achievements = await fetch_many(
        user_id=12345,
        page=1,
        page_size=10
    )
    
    # Check if user has specific achievement
    user_achievements = await fetch_many(
        user_id=12345,
        achievement_id=1
    )
    has_achievement = len(user_achievements) > 0

Related Files:
    - app/repositories/achievements.py: Achievement definitions
    - app/usecases/achievements.py: Achievement validation logic
    - app/objects/achievement.py: Achievement data model
    - app/repositories/users.py: User management integration
    - app/state/services.py: Database connection management
"""

from __future__ import annotations

from typing import TypedDict
from typing import cast

from sqlalchemy import Column
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import insert
from sqlalchemy import select

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.repositories import Base


class UserAchievementsTable(Base):
    __tablename__ = "user_achievements"

    userid = Column("userid", Integer, nullable=False, primary_key=True)
    achid = Column("achid", Integer, nullable=False, primary_key=True)

    __table_args__ = (
        Index("user_achievements_achid_index", achid),
        Index("user_achievements_userid_index", userid),
    )


READ_PARAMS = (
    UserAchievementsTable.userid,
    UserAchievementsTable.achid,
)


class UserAchievement(TypedDict):
    userid: int
    achid: int


async def create(user_id: int, achievement_id: int) -> UserAchievement:
    """Creates a new user achievement entry."""
    insert_stmt = insert(UserAchievementsTable).values(
        userid=user_id,
        achid=achievement_id,
    )
    await app.state.services.database.execute(insert_stmt)

    select_stmt = (
        select(*READ_PARAMS)
        .where(UserAchievementsTable.userid == user_id)
        .where(UserAchievementsTable.achid == achievement_id)
    )
    user_achievement = await app.state.services.database.fetch_one(select_stmt)
    assert user_achievement is not None
    return cast(UserAchievement, user_achievement)


async def fetch_many(
    user_id: int | _UnsetSentinel = UNSET,
    achievement_id: int | _UnsetSentinel = UNSET,
    page: int | None = None,
    page_size: int | None = None,
) -> list[UserAchievement]:
    """Fetch a list of user achievements."""
    select_stmt = select(*READ_PARAMS)
    if not isinstance(user_id, _UnsetSentinel):
        select_stmt = select_stmt.where(UserAchievementsTable.userid == user_id)
    if not isinstance(achievement_id, _UnsetSentinel):
        select_stmt = select_stmt.where(UserAchievementsTable.achid == achievement_id)

    if page and page_size:
        select_stmt = select_stmt.limit(page_size).offset((page - 1) * page_size)

    user_achievements = await app.state.services.database.fetch_all(select_stmt)
    return cast(list[UserAchievement], user_achievements)


# TODO: delete?
