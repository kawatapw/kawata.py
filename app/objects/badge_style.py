"""
Badge_Style Module - Badge Styling Configuration Data Model

This module defines the Badge_Style class, which represents styling configuration
for user badges in the osu! server application. Badge styles define how badges
are visually presented to users, including their appearance, colors, and other
visual properties.

The Badge_Style class serves as a data container for badge styling information,
allowing for flexible and customizable badge appearances. This enables the server
to support various badge designs and visual themes that can be applied to user
profiles and in-game displays.

Key Features:
    - Data container for badge styling configuration
    - Support for multiple style types and values
    - Integration with the badge system for visual customization
    - String representation for logging and debugging
    - Type hints for better code documentation and IDE support

Integration Points:
    - Badge management in app/repositories/badges.py
    - Player profile display in app/api/v2/players.py
    - Badge rendering in app/objects/badge.py
    - Database storage in app/repositories/badges.py
    - Administrative tools in app/api/v2/players.py

Badge Style Structure:
    - id: Unique identifier for the badge style
    - badge_id: Reference to the parent badge
    - type: Type of style property (e.g., "color", "border", "background")
    - value: Value of the style property (e.g., "#FF0000", "solid", "gradient")

Style Types:
    - color: Text or element color values
    - border: Border styling properties
    - background: Background color or image properties
    - font: Font family and styling properties
    - size: Dimension and sizing properties

Usage Pattern:
    - Badge styles are typically loaded from database or configuration
    - They are associated with specific badges via badge_id
    - Multiple styles can be applied to a single badge
    - Styles are used during badge rendering and display

Example Usage:
    # Create a badge style
    style = Badge_Style(
        id=1,
        badge_id=100,
        type="color",
        value="#FF0000"
    )

    # Access style properties
    style_type = style.type  # "color"
    style_value = style.value  # "#FF0000"

Related Files:
    - app/objects/badge.py: Badge class that uses badge styles
    - app/repositories/badges.py: Database operations for badges and styles
    - app/api/v2/players.py: Player profile display with badge styling
    - app/objects/player.py: Player class with badge associations
"""

from __future__ import annotations

__all__ = ("Badge_Style",)


class Badge_Style:
    """A class to represent a single Badge Style"""

    def __init__(
        self,
        id: int,
        badge_id: int,
        type: str,
        value: str,
    ) -> None:
        """A class representing one Badge Style."""
        self.id = id
        self.badge_id = badge_id
        self.type = type
        self.value = value

    def __repr__(self) -> str:
        return f"Badge_Style(id={self.id}, badge_id='{self.badge_id}', type='{self.type}', value={self.value})"
