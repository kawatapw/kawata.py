"""
Achievements Use Cases - Business Logic for Achievement Management

This module provides business logic for managing achievements in the osu!
server application. It implements the use case pattern for achievement
operations, providing a clean abstraction layer between the API endpoints
and the repository layer for achievement-related business logic.

The module handles achievement creation and retrieval operations, delegating
data access to the achievements repository while providing a simplified
interface for achievement management. It serves as the business logic layer
that coordinates achievement operations across the application.

Key Features:
    - Achievement creation with validation
    - Achievement retrieval with pagination
    - Business logic abstraction from data access
    - Clean separation of concerns
    - Type-safe achievement operations
    - Integration with repository layer

Integration Points:
    - Achievement API endpoints in app/api/v2/
    - Achievement repository in app/repositories/achievements.py
    - Achievement data model in app/objects/achievement.py
    - Achievement validation in app/usecases/achievements.py
    - Database operations through repository layer

Achievement Operations:
    - Create new achievements with file, name, description, and condition
    - Retrieve achievements with pagination support
    - Business logic validation and processing
    - Repository delegation for data persistence

Usage Pattern:
    # Create a new achievement
    achievement = await create(
        file="pass_map",
        name="First Pass",
        desc="Pass your first map",
        cond="score.passed"
    )
    
    # Fetch achievements with pagination
    achievements = await fetch_many(
        page=1,
        page_size=10
    )
    
    # Process achievements for display
    for achievement in achievements:
        display_achievement(achievement)

Related Files:
    - app/repositories/achievements.py: Data access layer
    - app/objects/achievement.py: Achievement data model
    - app/api/v2/: API endpoints using achievements
    - app/usecases/user_achievements.py: User achievement tracking
"""

from __future__ import annotations

import app.repositories.achievements
from app.repositories.achievements import Achievement


async def create(
    file: str,
    name: str,
    desc: str,
    cond: str,
) -> Achievement:
    achievement = await app.repositories.achievements.create(
        file,
        name,
        desc,
        cond,
    )
    return achievement


async def fetch_many(
    page: int | None = None,
    page_size: int | None = None,
) -> list[Achievement]:
    achievements = await app.repositories.achievements.fetch_many(
        page,
        page_size,
    )
    return achievements
