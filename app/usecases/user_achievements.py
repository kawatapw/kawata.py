"""
User Achievements Use Cases - Business Logic for User Achievement Tracking

This module provides business logic for tracking user achievements in the osu!
server application. It implements the use case pattern for user achievement
operations, providing a clean abstraction layer between the API endpoints
and the repository layer for user achievement-related business logic.

The module handles user achievement creation and retrieval operations,
delegating data access to the user achievements repository while providing
a simplified interface for user achievement management. It serves as the
business logic layer that coordinates user achievement operations across
the application.

Key Features:
    - User achievement creation with validation
    - User achievement retrieval with pagination
    - Business logic abstraction from data access
    - Clean separation of concerns
    - Type-safe user achievement operations
    - Integration with repository layer

Integration Points:
    - User achievement API endpoints in app/api/v2/
    - User achievement repository in app/repositories/user_achievements.py
    - Achievement data model in app/objects/achievement.py
    - User management in app/repositories/users.py
    - Achievement validation in app/usecases/achievements.py

User Achievement Operations:
    - Create new user achievements linking users to achievements
    - Retrieve user achievements with pagination support
    - Business logic validation and processing
    - Repository delegation for data persistence

Usage Pattern:
    # Create a new user achievement
    user_achievement = await create(
        user_id=12345,
        achievement_id=1
    )

    # Fetch user achievements with pagination
    user_achievements = await fetch_many(
        user_id=12345,
        page=1,
        page_size=10
    )

    # Process user achievements for display
    for user_achievement in user_achievements:
        display_user_achievement(user_achievement)

Related Files:
    - app/repositories/user_achievements.py: Data access layer
    - app/objects/achievement.py: Achievement data model
    - app/usecases/achievements.py: Achievement management
    - app/api/v2/: API endpoints using user achievements
"""

from __future__ import annotations

import app.repositories.user_achievements
from app._typing import UNSET, _UnsetSentinel
from app.repositories.user_achievements import UserAchievement


async def create(user_id: int, achievement_id: int) -> UserAchievement:
    user_achievement = await app.repositories.user_achievements.create(
        user_id,
        achievement_id,
    )
    return user_achievement


async def fetch_many(
    user_id: int | _UnsetSentinel = UNSET,
    page: int | None = None,
    page_size: int | None = None,
) -> list[UserAchievement]:
    user_achievements = await app.repositories.user_achievements.fetch_many(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    return user_achievements
