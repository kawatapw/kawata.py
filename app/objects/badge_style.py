from __future__ import annotations

from typing import TYPE_CHECKING

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.objects.player import Player

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
