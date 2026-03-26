"""
Badge Module - User Badge Data Model

This module defines the Badge class, which represents a user badge in the osu! server
application. Badges are visual indicators that can be awarded to players for various
achievements, contributions, or special status. They appear on player profiles and
serve as recognition for accomplishments or roles within the community.

The Badge class serves as a data container for badge information and maintains
associations with badge styles that define their visual appearance. This design
allows for flexible badge management with customizable visual properties.

Key Features:
    - Data container for badge metadata (ID, name, description, priority)
    - Association with badge styles for visual customization
    - Priority-based ordering for badge display
    - String representation for logging and debugging
    - Type hints for better code documentation and IDE support

Integration Points:
    - Badge management in app/repositories/badges.py
    - Player profile display in app/api/v2/players.py
    - Badge assignment in app/api/v2/players.py
    - Database storage in app/repositories/badges.py
    - Administrative tools in app/api/v2/players.py

Badge Structure:
    - id: Unique identifier for the badge
    - name: Display name of the badge
    - description: Description of what the badge represents
    - priority: Display priority (higher values shown first)
    - badge_styles: Set of Badge_Style objects defining visual appearance

Badge Types:
    - Achievement badges: Awarded for gameplay accomplishments
    - Role badges: Indicate special roles (moderator, developer, etc.)
    - Event badges: Awarded for participation in events
    - Donor badges: Recognition for financial support
    - Special badges: Unique badges for special circumstances

Usage Pattern:
    - Badges are typically loaded from database or configuration
    - They are associated with players via player ID
    - Badge styles define visual appearance properties
    - Priority determines display order on player profiles

Example Usage:
    # Create a badge
    badge = Badge(
        id=1,
        name="First Place",
        description="Awarded for achieving first place in a tournament",
        priority=10,
        badge_styles={gold_style, border_style}
    )

    # Access badge properties
    badge_name = badge.name  # "First Place"
    badge_priority = badge.priority  # 10

Related Files:
    - app/objects/badge_style.py: Badge styling configuration
    - app/repositories/badges.py: Database operations for badges
    - app/api/v2/players.py: Player profile display with badges
    - app/objects/player.py: Player class with badge associations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.objects.badge_style import Badge_Style

if TYPE_CHECKING:
    pass

__all__ = ("Badge",)


class Badge:
    """A class to represent a single bancho.py clan."""

    def __init__(
        self,
        id: int,
        name: str,
        description: str,
        priority: int,
        badge_styles: set[Badge_Style] | None = None,
    ) -> None:
        """A class representing one of bancho.py's clans."""
        self.id = id
        self.name = name
        self.description = description
        self.priority = priority

        if badge_styles is None:
            badge_styles = set()

        self.badge_styles = badge_styles  # userids

    def __repr__(self) -> str:
        return f"Badge(id={self.id}, name='{self.name}', description='{self.description}', priority={self.priority}, badge_styles={self.badge_styles})"
