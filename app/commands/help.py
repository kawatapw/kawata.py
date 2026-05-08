"""
Rich Help System for Commands

Provides formatted help messages with filtering, searching, and rich formatting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.commands.base import CommandCategory

if TYPE_CHECKING:
    from app.commands import CommandRegistry
    from app.commands.base import Command
    from app.objects.player import Player


def generate_help_message(
    registry: CommandRegistry,
    player: Player,
    category: CommandCategory | None = None,
    search_query: str | None = None,
) -> str:
    """
    Generate a rich help message for commands.

    Args:
        registry: Command registry
        player: Player requesting help
        category: Filter by category (optional)
        search_query: Search query (optional)

    Returns:
        Formatted help message
    """
    prefix = "!"

    # If search query provided, search and filter
    if search_query:
        return generate_search_results(registry, player, search_query, prefix)

    # If category provided, show category-specific help
    if category:
        return generate_category_help(registry, player, category, prefix)

    # Generate general help overview
    return generate_general_help(registry, player, prefix)


def generate_general_help(
    registry: CommandRegistry,
    player: Player,
    prefix: str,
) -> str:
    """Generate general help overview."""
    lines = [
        "Command Help System",
        "===================",
        "",
        f"Type '{prefix}help <command>' for detailed help on a specific command.",
        f"Type '{prefix}help <category>' for commands in a specific category.",
        f"Type '{prefix}help <search>' to search for commands.",
        "",
    ]

    # Get available commands for player
    available_commands = registry.get_available(player)

    # Group by category
    commands_by_category: dict[CommandCategory, list[Command]] = {}
    for cmd in available_commands:
        if cmd.metadata.hidden:
            continue
        if cmd.metadata.category not in commands_by_category:
            commands_by_category[cmd.metadata.category] = []
        commands_by_category[cmd.metadata.category].append(cmd)

    # Sort categories
    sorted_categories = sorted(
        commands_by_category.keys(),
        key=lambda c: c.value,
    )

    # Show categories and command count
    lines.append("Available command categories:")
    lines.append("-" * 40)

    for category in sorted_categories:
        category_commands = commands_by_category[category]
        category_name = category.value.title()
        cmd_list = ", ".join(sorted([cmd.metadata.name for cmd in category_commands]))
        lines.append(f"{category_name:20} ({len(category_commands)} commands)")
        lines.append(f"  Commands: {cmd_list}")
        lines.append("")

    # Show some examples
    lines.append("Example commands:")
    lines.append("-" * 40)

    # Show one example from each category
    for category in sorted_categories:
        category_commands = commands_by_category[category]
        if category_commands:
            cmd = category_commands[0]
            lines.append(
                f"  !{cmd.metadata.name:15} - {cmd.metadata.description or 'No description'}"
            )

    return "\n".join(lines)


def generate_category_help(
    registry: CommandRegistry,
    player: Player,
    category: CommandCategory,
    prefix: str,
) -> str:
    """Generate help for a specific category."""
    category_commands = registry.get_by_category(category)

    # Filter by player privileges
    available_commands = [
        cmd
        for cmd in category_commands
        if player.priv & cmd.privileges == cmd.privileges and not cmd.metadata.hidden
    ]

    if not available_commands:
        return f"No commands available in category '{category.value}' for your privilege level."

    lines = [
        f"{category.value.title()} Commands",
        "=" * 50,
        "",
    ]

    # Sort commands by name
    for cmd in sorted(available_commands, key=lambda c: c.metadata.name):
        lines.append(f"!{cmd.metadata.name}")
        if cmd.metadata.description:
            lines.append(f"  {cmd.metadata.description}")
        if cmd.metadata.usage:
            lines.append(f"  Usage: {cmd.metadata.usage}")
        if cmd.metadata.examples:
            lines.append("  Examples:")
            for example in cmd.metadata.examples:
                lines.append(f"    {example}")
        lines.append("")

    return "\n".join(lines)


def generate_command_help(
    registry: CommandRegistry,
    player: Player,
    command_name: str,
    prefix: str,
) -> str:
    """Generate help for a specific command."""
    cmd = registry.get_by_trigger(command_name)

    if not cmd:
        # Check for namespace command
        parts = command_name.split()
        if len(parts) == 2:
            cmd = registry.get_by_namespace(parts[0], parts[1])

    if not cmd:
        return f"Command '{command_name}' not found."

    # Check privileges
    if player.priv & cmd.privileges != cmd.privileges:
        return f"Command '{command_name}' not found."

    lines = [
        f"Command: !{cmd.metadata.name}",
        "=" * 50,
        "",
    ]

    if cmd.metadata.description:
        lines.append(f"Description: {cmd.metadata.description}")
        lines.append("")

    if cmd.metadata.usage:
        lines.append(f"Usage: {cmd.metadata.usage}")
        lines.append("")

    # Show all triggers/aliases
    if len(cmd.metadata.triggers) > 1:
        lines.append(f"Aliases: {', '.join(cmd.metadata.triggers[1:])}")
        lines.append("")

    # Show category
    lines.append(f"Category: {cmd.metadata.category.value.title()}")

    # Show privileges
    from app.constants.privileges import Privileges

    priv_names: list[str] = []
    for priv in Privileges:
        if priv.value != 0 and cmd.privileges & priv.value:
            priv_names.append(str(priv.name))
    if priv_names:
        lines.append(f"Required privileges: {', '.join(priv_names)}")

    lines.append("")

    # Show examples
    if cmd.metadata.examples:
        lines.append("Examples:")
        for example in cmd.metadata.examples:
            lines.append(f"  {example}")
        lines.append("")

    # Show detailed help
    if cmd.metadata.detailed_help:
        lines.append("Detailed Help:")
        lines.append("-" * 50)
        lines.append(cmd.metadata.detailed_help)
        lines.append("")

    # Show deprecation warning if applicable
    if cmd.metadata.deprecated:
        lines.append("⚠️  This command is deprecated.")
        if cmd.metadata.deprecation_message:
            lines.append(f"   {cmd.metadata.deprecation_message}")

    return "\n".join(lines)


def generate_search_results(
    registry: CommandRegistry,
    player: Player,
    search_query: str,
    prefix: str,
) -> str:
    """Generate search results for commands."""
    query_lower = search_query.lower()
    available_commands = registry.get_available(player)

    # Find matching commands
    matches = []
    for cmd in available_commands:
        if cmd.metadata.hidden:
            continue

        # Check triggers
        for trigger in cmd.metadata.triggers:
            if query_lower in trigger.lower():
                matches.append(cmd)
                break
        else:
            # Check description
            if (
                cmd.metadata.description
                and query_lower in cmd.metadata.description.lower()
            ):
                matches.append(cmd)

    if not matches:
        return f"No commands found matching '{search_query}'."

    lines = [
        f"Search results for '{search_query}':",
        "=" * 50,
        "",
    ]

    # Group matches by category
    matches_by_category: dict[CommandCategory, list[Command]] = {}
    for cmd in matches:
        if cmd.metadata.category not in matches_by_category:
            matches_by_category[cmd.metadata.category] = []
        matches_by_category[cmd.metadata.category].append(cmd)

    # Sort by category
    sorted_categories = sorted(matches_by_category.keys(), key=lambda c: c.value)

    for category in sorted_categories:
        category_matches = matches_by_category[category]
        lines.append(f"{category.value.title()} Commands:")
        lines.append("-" * 30)

        for cmd in sorted(category_matches, key=lambda c: c.metadata.name):
            lines.append(f"  !{cmd.metadata.name}")
            if cmd.metadata.description:
                lines.append(f"    {cmd.metadata.description}")
            if cmd.metadata.usage:
                lines.append(f"    Usage: {cmd.metadata.usage}")
            if cmd.metadata.examples:
                lines.append("    Examples:")
                for example in cmd.metadata.examples:
                    lines.append(f"      {example}")

        lines.append("")

    return "\n".join(lines)
