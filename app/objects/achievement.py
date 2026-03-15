"""
Achievement Module - osu! Achievement Data Model

This module defines the Achievement class, which represents a single osu! achievement
that players can unlock during gameplay. Achievements are special milestones or
accomplishments that players can earn by meeting specific conditions during their
gameplay sessions.

The Achievement class serves as a data container for achievement metadata and
provides a callable condition function that determines when the achievement should
be unlocked. This design allows for flexible achievement logic that can be evaluated
dynamically based on player performance and game state.

Key Features:
    - Data container for achievement metadata (ID, file, name, description)
    - Callable condition function for dynamic achievement evaluation
    - Integration with the score system for achievement validation
    - String representation for logging and debugging
    - Type hints for better code documentation and IDE support

Integration Points:
    - Achievement validation in app/usecases/achievements.py
    - Score submission handling in app/api/domains/osu.py
    - Player achievement tracking in app/repositories/user_achievements.py
    - Achievement display in app/api/v2/players.py
    - Database storage in app/repositories/achievements.py

Achievement Structure:
    - id: Unique identifier for the achievement
    - file: Filename or identifier for achievement assets
    - name: Display name of the achievement
    - desc: Description of how to unlock the achievement
    - cond: Callable condition function that evaluates achievement unlock

Condition Function:
    - Takes a Score object and game mode as parameters
    - Returns True if the achievement should be unlocked
    - Can access score data, player stats, and game mode information
    - Allows for complex achievement logic based on multiple factors

Usage Pattern:
    - Achievements are typically loaded from configuration or database
    - The condition function is called during score submission
    - If condition returns True, the achievement is unlocked for the player
    - Achievement data is stored in player achievement records

Example Usage:
    # Create an achievement
    achievement = Achievement(
        id=1,
        file="pass_map",
        name="First Pass",
        desc="Pass your first map",
        cond=lambda score, mode: score.passed
    )
    
    # Check if achievement should be unlocked
    if achievement.cond(score, game_mode):
        unlock_achievement(player, achievement)

Related Files:
    - app/usecases/achievements.py: Achievement validation logic
    - app/objects/score.py: Score class used in condition evaluation
    - app/repositories/achievements.py: Database operations for achievements
    - app/repositories/user_achievements.py: Player achievement tracking
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.objects.score import Score


class Achievement:
    """A class to represent a single osu! achievement."""

    def __init__(
        self,
        id: int,
        file: str,
        name: str,
        desc: str,
        cond: Callable[[Score, int], bool],  # (score, mode) -> unlocked
    ) -> None:
        self.id = id
        self.file = file
        self.name = name
        self.desc = desc

        self.cond = cond

    def __repr__(self) -> str:
        return f"{self.file}+{self.name}+{self.desc}"
