from __future__ import annotations

from typing import TYPE_CHECKING

from typing import TYPE_CHECKING
from typing import Optional
from app.objects.badge_style import Badge_Style

if TYPE_CHECKING:
    from app.objects.player import Player

__all__ = ("Badge",)


class Badge:
    """A class to represent a single bancho.py clan."""

    def __init__(
        self,
        id: int,
        name: str,
        description: str,
        priority: int,
        badge_styles: Optional[set[Badge_Style]] = None,
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
