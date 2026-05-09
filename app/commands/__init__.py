"""
Command Registry and Processor

Central command registry that manages all commands, handles execution,
validation, and provides command discovery features.
"""

from __future__ import annotations

import inspect
import traceback
from collections.abc import Awaitable
from typing import TYPE_CHECKING
from typing import Any

from app.commands.base import Command
from app.commands.base import CommandCategory
from app.commands.base import CommandError
from app.commands.base import ValidationError

# Import all command categories
from app.commands.categories import _map
from app.commands.categories import _with
from app.commands.categories import addnote
from app.commands.categories import addpriv
from app.commands.categories import alert
from app.commands.categories import alertuser
from app.commands.categories import apikey
from app.commands.categories import block
from app.commands.categories import changename
from app.commands.categories import clan_create
from app.commands.categories import clan_disband
from app.commands.categories import clan_help
from app.commands.categories import clan_info
from app.commands.categories import clan_leave
from app.commands.categories import clan_list
from app.commands.categories import debug
from app.commands.categories import debug_focus
from app.commands.categories import givedonator
from app.commands.categories import help_cmd
from app.commands.categories import maplink
from app.commands.categories import mp_abort
from app.commands.categories import mp_addref
from app.commands.categories import mp_condition
from app.commands.categories import mp_endscrim
from app.commands.categories import mp_force
from app.commands.categories import mp_freemods
from app.commands.categories import mp_help
from app.commands.categories import mp_host
from app.commands.categories import mp_invite
from app.commands.categories import mp_listref
from app.commands.categories import mp_loadpool
from app.commands.categories import mp_lock
from app.commands.categories import mp_map
from app.commands.categories import mp_mods
from app.commands.categories import mp_randpw
from app.commands.categories import mp_rematch
from app.commands.categories import mp_rmref
from app.commands.categories import mp_scrim
from app.commands.categories import mp_start
from app.commands.categories import mp_teams
from app.commands.categories import mp_unloadpool
from app.commands.categories import mp_unlock
from app.commands.categories import notes  # Moderator commands
from app.commands.categories import pool_add
from app.commands.categories import pool_create
from app.commands.categories import pool_delete
from app.commands.categories import pool_help
from app.commands.categories import pool_info
from app.commands.categories import pool_list
from app.commands.categories import pool_remove
from app.commands.categories import py
from app.commands.categories import recalc
from app.commands.categories import recalc_season_stats
from app.commands.categories import recent
from app.commands.categories import reconnect
from app.commands.categories import reload
from app.commands.categories import request
from app.commands.categories import requests  # Nominator commands
from app.commands.categories import restrict
from app.commands.categories import rmpriv
from app.commands.categories import roll
from app.commands.categories import season_create
from app.commands.categories import season_end
from app.commands.categories import season_list
from app.commands.categories import season_schedule
from app.commands.categories import season_start
from app.commands.categories import seasons
from app.commands.categories import seasons_all
from app.commands.categories import server
from app.commands.categories import shutdown
from app.commands.categories import silence
from app.commands.categories import stealth  # Developer commands
from app.commands.categories import switchserv
from app.commands.categories import top
from app.commands.categories import unblock
from app.commands.categories import unrestrict
from app.commands.categories import unsilence
from app.commands.categories import (
    # Administrator commands - user is imported separately from administrator module
    wipemap,
)
from app.commands.categories.administrator import user
from app.commands.context import CommandResponse
from app.commands.context import Context
from app.commands.help import generate_help_message

if TYPE_CHECKING:
    from app.adapters.database import Database
    from app.objects.channel import Channel
    from app.objects.player import Player
    from app.state import State


class CommandRegistry:
    """
    Central command registry for managing and executing commands.

    Provides:
    - Command registration and storage
    - Command discovery and filtering
    - Command execution with validation and hooks
    - Rich help system
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._namespaces: dict[str, dict[str, Command]] = {}
        self._categories: dict[CommandCategory, list[Command]] = {}

    def register(self, command: Command) -> None:
        """
        Register a command with the registry.

        Args:
            command: Command to register

        Raises:
            ValueError: If command with same trigger already exists
        """
        # Register command by all triggers
        for trigger in command.metadata.triggers:
            # For namespaced commands, register with namespace prefix to avoid conflicts
            if command.metadata.namespace:
                full_trigger = f"{command.metadata.namespace}_{trigger}"
            else:
                full_trigger = trigger

            if full_trigger in self._commands:
                raise ValueError(
                    f"Command with trigger '{full_trigger}' already registered"
                )
            self._commands[full_trigger] = command

        # Register by namespace if applicable
        if command.metadata.namespace:
            if command.metadata.namespace not in self._namespaces:
                self._namespaces[command.metadata.namespace] = {}
            self._namespaces[command.metadata.namespace][command.metadata.name] = (
                command
            )

        # Register by category
        if command.metadata.category not in self._categories:
            self._categories[command.metadata.category] = []
        self._categories[command.metadata.category].append(command)

    def get_by_trigger(self, trigger: str) -> Command | None:
        """Get command by trigger."""
        return self._commands.get(trigger)

    def get_by_namespace(self, namespace: str, name: str) -> Command | None:
        """Get command by namespace and name."""
        if namespace in self._namespaces:
            return self._namespaces[namespace].get(name)
        return None

    def get_by_category(self, category: CommandCategory) -> list[Command]:
        """Get all commands in a category."""
        return self._categories.get(category, [])

    def get_available(self, player: Player) -> list[Command]:
        """Get all commands available to a player."""
        return [
            cmd
            for cmd in self._commands.values()
            if player.priv & cmd.privileges == cmd.privileges
        ]

    def get_all_commands(self) -> list[Command]:
        """Get all registered commands."""
        return list(self._commands.values())

    async def execute(
        self,
        player: Player,
        recipient: Channel | Player,
        message: str,
        database: Database,
        cache: Any,
        settings: Any,
        state: State,
    ) -> CommandResponse | None:
        """
        Execute a command from a message.

        Args:
            player: Player executing the command
            recipient: Where the command was sent
            message: Full message text
            database: Database connection
            cache: Cache instance
            settings: Settings instance
            state: Application state

        Returns:
            CommandResponse or None if not a command
        """
        prefix = settings.COMMAND_PREFIX
        if not message.startswith(prefix):
            return None

        # Parse command and arguments
        parts = message[len(prefix) :].strip().split()
        if not parts:
            return None

        trigger = parts[0].lower()
        args = parts[1:]

        # Find command
        command = self.get_by_trigger(trigger)
        if not command:
            # Check for namespace command (e.g., "mp start")
            if len(args) > 0:
                namespace_command = self.get_by_namespace(trigger, args[0].lower())
                if namespace_command:
                    command = namespace_command
                    args = args[1:]

        # If still not found, check for namespaced trigger format (e.g., "mp_help")
        if not command and len(args) > 0:
            # Try to find a command with namespace_trigger format
            # e.g., "!mp help" should look for "mp_help" trigger
            namespaced_trigger = f"{trigger}_{args[0].lower()}"
            command = self.get_by_trigger(namespaced_trigger)
            if command:
                # Found a namespaced command, remove the subcommand from args
                args = args[1:]

        if not command:
            return None

        # Check privileges
        # The command's privileges must be a subset of the player's privileges
        # This means the player must have ALL the privileges required by the command
        if (player.priv & command.privileges) != command.privileges:
            return CommandResponse(
                resp="You don't have permission to use this command."
            )

        # Check if command is enabled
        if not command.metadata.enabled:
            return CommandResponse(resp="This command is currently disabled.")

        # Check if command is deprecated
        if command.metadata.deprecated:
            msg = "This command is deprecated."
            if command.metadata.deprecation_message:
                msg += f" {command.metadata.deprecation_message}"
            return CommandResponse(resp=msg)

        # Create context
        context = Context(
            player=player,
            trigger=trigger,
            args=args,
            recipient=recipient,
            raw_message=message,
            database=database,
            cache=cache,
            settings=settings,
            state=state,
            command=command,
        )

        try:
            # Run pre-execution hooks
            for hook in command.metadata.pre_hooks:
                try:
                    await hook(context)
                except CommandError as e:
                    return CommandResponse(resp=str(e))

            # Validate arguments
            for validator in command.metadata.validators:
                try:
                    # Check if the validator itself is a coroutine function
                    # or if its __call__ method is a coroutine function
                    is_async = inspect.iscoroutinefunction(
                        validator
                    ) or inspect.iscoroutinefunction(validator.__call__)
                    if is_async:
                        result = validator(context)
                        if inspect.isawaitable(result):
                            await result
                    else:
                        validator(context)
                except ValidationError as e:
                    return CommandResponse(resp=f"Validation error: {e}")

            # Execute command
            result = await command.callback(context)

            # Run post-execution hooks
            for hook in command.metadata.post_hooks:
                try:
                    # post_hooks may accept (Context, str | None) or just (Context)
                    sig = inspect.signature(hook)
                    if len(sig.parameters) >= 2:
                        await hook(context, result)
                    else:
                        await hook(context)
                except Exception:
                    # Log but don't fail the command
                    traceback.print_exc()

            # Format response with timing
            if result is not None:
                return CommandResponse(resp=result)

            return CommandResponse(resp=None)

        except CommandError as e:
            return CommandResponse(resp=f"Error: {e}")
        except Exception:
            traceback.print_exc()
            return CommandResponse(
                resp="An unexpected error occurred while executing the command."
            )

    def generate_help(
        self,
        player: Player,
        category: CommandCategory | None = None,
        search_query: str | None = None,
    ) -> str:
        """
        Generate help message for commands.

        Args:
            player: Player requesting help
            category: Filter by category (optional)
            search_query: Search query (optional)

        Returns:
            Formatted help message
        """
        return generate_help_message(self, player, category, search_query)

    def generate_docs(self) -> str:
        """Generate markdown documentation for all commands."""
        lines = ["# Command Reference\n"]

        for category in CommandCategory:
            category_commands = self.get_by_category(category)
            if not category_commands:
                continue

            lines.append(f"\n## {category.value.title()} Commands\n")

            for cmd in sorted(category_commands, key=lambda c: c.metadata.name):
                if cmd.metadata.hidden:
                    continue

                lines.append(f"\n### !{cmd.metadata.name}")

                if cmd.metadata.description:
                    lines.append(cmd.metadata.description)

                if cmd.metadata.usage:
                    lines.append(f"\n**Usage:** {cmd.metadata.usage}")

                lines.append(f"**Privileges:** {cmd.privileges}")

                if cmd.metadata.examples:
                    lines.append("\n**Examples:**")
                    for example in cmd.metadata.examples:
                        lines.append(f"  {example}")

                if cmd.metadata.detailed_help:
                    lines.append(f"\n{cmd.metadata.detailed_help}")

        return "\n".join(lines)


# Global registry instance
_registry: CommandRegistry = CommandRegistry()


def get_registry() -> CommandRegistry:
    """Get the global command registry."""
    return _registry


def register_command(command: Command) -> None:
    """Register a command with the global registry."""
    _registry.register(command)


def execute_command(
    player: Player,
    recipient: Channel | Player,
    message: str,
    database: Database,
    cache: Any,
    settings: Any,
    state: State,
) -> Awaitable[CommandResponse | None]:
    """Execute a command using the global registry."""
    return _registry.execute(
        player, recipient, message, database, cache, settings, state
    )


def generate_help(
    player: Player,
    category: CommandCategory | None = None,
    search_query: str | None = None,
) -> str:
    """Generate help message using the global registry."""
    return _registry.generate_help(player, category, search_query)


# Register all imported commands
def _register_all_commands() -> None:
    """Register all command functions with the registry."""
    # User commands
    _registry.register(help_cmd)
    _registry.register(roll)
    _registry.register(recent)
    _registry.register(top)
    _registry.register(block)
    _registry.register(unblock)
    _registry.register(reconnect)
    _registry.register(changename)
    _registry.register(maplink)
    _registry.register(_with)
    _registry.register(request)
    _registry.register(apikey)

    # Nominator commands
    _registry.register(requests)
    _registry.register(_map)

    # Moderator commands
    _registry.register(notes)
    _registry.register(addnote)
    _registry.register(silence)
    _registry.register(unsilence)

    # Administrator commands
    _registry.register(user)
    _registry.register(restrict)
    _registry.register(unrestrict)
    _registry.register(alert)
    _registry.register(alertuser)
    _registry.register(switchserv)
    _registry.register(shutdown)

    # Developer commands
    _registry.register(stealth)
    _registry.register(recalc)
    _registry.register(debug)
    _registry.register(debug_focus)
    _registry.register(addpriv)
    _registry.register(rmpriv)
    _registry.register(givedonator)
    _registry.register(wipemap)
    _registry.register(reload)
    _registry.register(server)
    _registry.register(py)

    # Multiplayer commands
    _registry.register(mp_help)
    _registry.register(mp_start)
    _registry.register(mp_abort)
    _registry.register(mp_map)
    _registry.register(mp_mods)
    _registry.register(mp_freemods)
    _registry.register(mp_host)
    _registry.register(mp_randpw)
    _registry.register(mp_invite)
    _registry.register(mp_addref)
    _registry.register(mp_rmref)
    _registry.register(mp_listref)
    _registry.register(mp_lock)
    _registry.register(mp_unlock)
    _registry.register(mp_teams)
    _registry.register(mp_condition)
    _registry.register(mp_scrim)
    _registry.register(mp_endscrim)
    _registry.register(mp_rematch)
    _registry.register(mp_force)
    _registry.register(mp_loadpool)
    _registry.register(mp_unloadpool)

    # Mappool commands
    _registry.register(pool_help)
    _registry.register(pool_create)
    _registry.register(pool_delete)
    _registry.register(pool_add)
    _registry.register(pool_remove)
    _registry.register(pool_list)
    _registry.register(pool_info)

    # Clan commands
    _registry.register(clan_help)
    _registry.register(clan_create)
    _registry.register(clan_disband)
    _registry.register(clan_info)
    _registry.register(clan_leave)
    _registry.register(clan_list)

    # Season commands
    _registry.register(season_create)
    _registry.register(season_start)
    _registry.register(season_end)
    _registry.register(recalc_season_stats)
    _registry.register(season_list)
    _registry.register(season_schedule)
    _registry.register(seasons)
    _registry.register(seasons_all)


# Initialize command registry on import
_register_all_commands()
