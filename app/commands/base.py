"""
Command Base Classes and Decorators

This module provides the core foundation for the command system,
including command classes, decorators, and metadata structures.
"""

from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol

if TYPE_CHECKING:
    from app.commands.context import Context


class CommandCategory(Enum):
    """Categories for organizing commands."""

    USER = "user"
    NOMINATOR = "nominator"
    MODERATOR = "moderator"
    ADMINISTRATOR = "administrator"
    DEVELOPER = "developer"
    MULTIPLAYER = "multiplayer"
    MAPPOOL = "mappool"
    CLAN = "clan"
    SEASON = "season"


class CommandError(Exception):
    """Exception raised when a command encounters an error."""

    pass


class ValidationError(CommandError):
    """Exception raised when command validation fails."""

    pass


class CommandValidator(Protocol):
    """Protocol for command validators."""

    def __call__(self, ctx: Context, *args: Any) -> Any: ...


@dataclass
class CommandMetadata:
    """Metadata for a command."""

    name: str
    triggers: list[str]
    category: CommandCategory
    namespace: str | None = None

    # Documentation
    description: str | None = None
    detailed_help: str | None = None
    examples: list[str] = field(default_factory=list)
    usage: str | None = None

    # Configuration
    hidden: bool = False
    enabled: bool = True
    deprecated: bool = False
    deprecation_message: str | None = None

    # Validation
    validators: list[CommandValidator] = field(default_factory=list)

    # Metadata
    author: str | None = None
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)

    # Pipeline
    pre_hooks: list[Callable[[Context], Awaitable[None]]] = field(default_factory=list)
    post_hooks: list[Callable[..., Awaitable[None]]] = field(default_factory=list)


@dataclass
class Command:
    """Represents a command with all its metadata."""

    metadata: CommandMetadata
    callback: Callable[[Context], Awaitable[str | None]]
    privileges: int  # Bitmask of required privileges

    def __post_init__(self) -> None:
        """Validate command configuration."""
        if not self.metadata.triggers:
            raise ValueError("Command must have at least one trigger")
        if not self.metadata.name:
            raise ValueError("Command must have a name")


class CommandBuilder:
    """Builder pattern for creating commands with fluent API."""

    def __init__(self, name: str, category: CommandCategory):
        self.metadata = CommandMetadata(name=name, triggers=[name], category=category)
        self._privileges = 0
        self.callback: Callable[[Context], Awaitable[str | None]] | None = None

    def trigger(self, *triggers: str) -> CommandBuilder:
        """Add triggers/aliases for the command."""
        self.metadata.triggers = list(triggers)
        return self

    def privileges(self, privileges: int) -> CommandBuilder:
        """Set required privileges."""
        self._privileges = privileges
        return self

    def description(self, desc: str) -> CommandBuilder:
        """Set command description."""
        self.metadata.description = desc
        return self

    def detailed_help(self, help_text: str) -> CommandBuilder:
        """Set detailed help text."""
        self.metadata.detailed_help = help_text
        return self

    def examples(self, *examples: str) -> CommandBuilder:
        """Add usage examples."""
        self.metadata.examples = list(examples)
        return self

    def usage(self, usage: str) -> CommandBuilder:
        """Set usage syntax."""
        self.metadata.usage = usage
        return self

    def hidden(self, hidden: bool = True) -> CommandBuilder:
        """Set hidden flag."""
        self.metadata.hidden = hidden
        return self

    def namespace(self, namespace: str) -> CommandBuilder:
        """Set namespace for grouped commands."""
        self.metadata.namespace = namespace
        return self

    def validator(self, validator: CommandValidator) -> CommandBuilder:
        """Add a validator."""
        self.metadata.validators.append(validator)
        return self

    def pre_hook(self, hook: Callable[[Context], Awaitable[None]]) -> CommandBuilder:
        """Add a pre-execution hook."""
        self.metadata.pre_hooks.append(hook)
        return self

    def post_hook(
        self,
        hook: (
            Callable[[Context, str | None], Awaitable[None]]
            | Callable[[Context], Awaitable[None]]
        ),
    ) -> CommandBuilder:
        """Add a post-execution hook."""
        self.metadata.post_hooks.append(hook)
        return self

    def build(self, callback: Callable[[Context], Awaitable[str | None]]) -> Command:
        """Build the command with the provided callback."""
        self.callback = callback
        return Command(
            metadata=self.metadata,
            callback=callback,
            privileges=self._privileges,
        )


def command(
    name: str,
    category: CommandCategory,
    privileges_level: int = 0,
    triggers: list[str] | None = None,
    description: str | None = None,
    detailed_help: str | None = None,
    examples: list[str] | None = None,
    usage: str | None = None,
    hidden: bool = False,
    namespace: str | None = None,
    validators: list[CommandValidator] | None = None,
    pre_hooks: list[Callable[[Context], Awaitable[None]]] | None = None,
    post_hooks: list[Callable[..., Awaitable[None]]] | None = None,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """
    Decorator for registering commands.

    Args:
        name: Primary name of the command
        category: Command category
        privileges_level: Required privilege level (bitmask)
        triggers: List of triggers/aliases (defaults to [name])
        description: Short description
        detailed_help: Detailed help text
        examples: Usage examples
        usage: Usage syntax
        hidden: Whether to hide from help
        namespace: Namespace for grouped commands (e.g., "mp", "pool")
        validators: List of validators
        pre_hooks: Pre-execution hooks
        post_hooks: Post-execution hooks

    Returns:
        Decorator function that creates a Command
    """
    builder = CommandBuilder(name, category)

    if triggers:
        builder.trigger(*triggers)
    else:
        builder.trigger(name)

    builder.privileges(privileges_level)

    if description:
        builder.description(description)

    if detailed_help:
        builder.detailed_help(detailed_help)

    if examples:
        builder.examples(*examples)

    if usage:
        builder.usage(usage)

    if hidden:
        builder.hidden(True)

    if namespace:
        builder.namespace(namespace)

    if validators:
        for validator in validators:
            builder.validator(validator)

    if pre_hooks:
        for hook in pre_hooks:
            builder.pre_hook(hook)

    if post_hooks:
        for hook in post_hooks:
            builder.post_hook(hook)

    def decorator(callback: Callable[[Context], Awaitable[str | None]]) -> Command:
        return builder.build(callback)

    return decorator


# Convenience decorators for common categories
def user_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for user-level commands."""
    from app.constants.privileges import Privileges

    return command(
        category=CommandCategory.USER,
        privileges_level=Privileges.UNRESTRICTED,
        **kwargs,
    )


def nominator_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for nominator-level commands."""
    from app.constants.privileges import Privileges

    return command(
        category=CommandCategory.NOMINATOR,
        privileges_level=Privileges.NOMINATOR,
        **kwargs,
    )


def moderator_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for moderator-level commands."""
    from app.constants.privileges import Privileges

    return command(
        category=CommandCategory.MODERATOR,
        privileges_level=Privileges.MODERATOR,
        **kwargs,
    )


def administrator_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for administrator-level commands."""
    from app.constants.privileges import Privileges

    return command(
        category=CommandCategory.ADMINISTRATOR,
        privileges_level=Privileges.ADMINISTRATOR,
        **kwargs,
    )


def developer_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for developer-level commands."""
    from app.constants.privileges import Privileges

    return command(
        category=CommandCategory.DEVELOPER,
        privileges_level=Privileges.DEVELOPER,
        **kwargs,
    )


def multiplayer_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for multiplayer commands."""
    return command(category=CommandCategory.MULTIPLAYER, namespace="mp", **kwargs)


def mappool_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for mappool commands."""
    return command(category=CommandCategory.MAPPOOL, namespace="pool", **kwargs)


def clan_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for clan commands."""
    return command(category=CommandCategory.CLAN, namespace="clan", **kwargs)


def season_command(
    **kwargs: Any,
) -> Callable[[Callable[[Context], Awaitable[str | None]]], Command]:
    """Decorator for season commands."""
    return command(category=CommandCategory.SEASON, namespace="season", **kwargs)
