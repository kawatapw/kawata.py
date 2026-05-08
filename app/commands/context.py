"""
Command Context with Dependency Injection

Provides the enhanced context that commands receive, including
dependency injection for database, cache, settings, and state.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    # Cache and Settings are modules, not classes, so we use Any for type hints
    from typing import Any

    from app.adapters.database import Database
    from app.commands.base import Command
    from app.objects.channel import Channel
    from app.objects.player import Player
    from app.state import State

    Cache = Any
    Settings = Any


@dataclass
class CommandResponse:
    """Response from a command execution."""

    resp: str | None
    hidden: bool = False
    silence_duration: float | None = None


@dataclass
class Context:
    """
    Enhanced command context with dependency injection.

    This provides commands with access to all necessary dependencies
    without requiring direct imports or global state access.
    """

    # Core command information
    player: Player
    trigger: str
    args: Sequence[str]
    recipient: Channel | Player
    raw_message: str

    # Dependency injection
    database: Database
    cache: Cache  # Will be defined in state
    settings: Settings  # Will be defined in state
    state: State

    # Command metadata
    command: Command | None = None

    # Parsed durations for duration validators
    parsed_durations: dict[int, float] | None = None

    # Helper methods
    async def get_player(self, name: str) -> Player | None:
        """
        Get a player by name with caching.

        Args:
            name: Player username

        Returns:
            Player object if found, None otherwise
        """
        return cast(Player | None, await self.state.sessions.players.from_cache_or_sql(name=name))

    async def get_player_by_id(self, player_id: int) -> Player | None:
        """
        Get a player by ID with caching.

        Args:
            player_id: Player ID

        Returns:
            Player object if found, None otherwise
        """
        return cast(Player | None, await self.state.sessions.players.from_cache_or_sql(id=player_id))

    def reply(self, message: str, hidden: bool = False) -> CommandResponse:
        """
        Create a command response.

        Args:
            message: Response message
            hidden: Whether the response should be hidden from others

        Returns:
            CommandResponse object
        """
        return CommandResponse(resp=message, hidden=hidden)

    def error(self, message: str) -> CommandResponse:
        """
        Create an error response.

        Args:
            message: Error message

        Returns:
            CommandResponse with error message
        """
        return self.reply(f"Error: {message}")

    def success(self, message: str) -> CommandResponse:
        """
        Create a success response.

        Args:
            message: Success message

        Returns:
            CommandResponse with success message
        """
        return self.reply(message)

    def usage_error(self, usage: str, message: str | None = None) -> CommandResponse:
        """
        Create a usage error response.

        Args:
            usage: Correct usage syntax
            message: Additional error message

        Returns:
            CommandResponse with usage information
        """
        if message:
            return self.reply(f"Invalid usage: {message}\nUsage: {usage}")
        return self.reply(f"Usage: {usage}")

    @property
    def has_args(self) -> bool:
        """Check if command has any arguments."""
        return len(self.args) > 0

    @property
    def arg_count(self) -> int:
        """Get the number of arguments."""
        return len(self.args)

    def get_arg(self, index: int, default: str | None = None) -> str | None:
        """
        Get argument by index with optional default.

        Args:
            index: Argument index
            default: Default value if argument doesn't exist

        Returns:
            Argument value or default
        """
        if index < len(self.args):
            return self.args[index]
        return default

    def join_args(self, start: int = 0, end: int | None = None, sep: str = " ") -> str:
        """
        Join multiple arguments into a single string.

        Args:
            start: Starting index
            end: Ending index (exclusive)
            sep: Separator

        Returns:
            Joined string
        """
        if end is None:
            return sep.join(self.args[start:])
        return sep.join(self.args[start:end])
