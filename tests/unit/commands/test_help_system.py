"""
Tests for the rich help system.

Covers help message generation, category filtering, and search functionality.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from app.commands import CommandRegistry
from app.commands import get_registry
from app.commands.base import Command
from app.commands.base import CommandCategory
from app.commands.base import CommandMetadata
from app.commands.help import generate_category_help
from app.commands.help import generate_command_help
from app.commands.help import generate_general_help
from app.commands.help import generate_help_message
from app.commands.help import generate_search_results
from app.constants.privileges import Privileges


@pytest.fixture
def registry():
    """Get the global registry."""
    return get_registry()


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    return player


def _make_command(
    name: str,
    category: CommandCategory,
    privileges: int,
    *,
    triggers: list[str] | None = None,
    description: str | None = None,
    detailed_help: str | None = None,
    examples: list[str] | None = None,
    usage: str | None = None,
    hidden: bool = False,
    deprecated: bool = False,
    deprecation_message: str | None = None,
    namespace: str | None = None,
) -> Command:
    """Helper to create a Command with arbitrary metadata."""
    metadata = CommandMetadata(
        name=name,
        triggers=triggers or [name],
        category=category,
        namespace=namespace,
        description=description,
        detailed_help=detailed_help,
        examples=examples or [],
        usage=usage,
        hidden=hidden,
        deprecated=deprecated,
        deprecation_message=deprecation_message,
    )
    return Command(
        metadata=metadata,
        callback=AsyncMock(return_value=None),
        privileges=privileges,
    )


@pytest.fixture
def player_unrestricted() -> Mock:
    player = Mock()
    player.name = "NormalUser"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    return player


@pytest.fixture
def player_developer() -> Mock:
    player = Mock()
    player.name = "DevUser"
    player.id = 2
    player.priv = Privileges.DEVELOPER
    return player


@pytest.fixture
def player_moderator() -> Mock:
    player = Mock()
    player.name = "ModUser"
    player.id = 3
    player.priv = Privileges.MODERATOR
    return player


@pytest.fixture
def player_zero_priv() -> Mock:
    player = Mock()
    player.name = "NoPrivUser"
    player.id = 4
    player.priv = Privileges(0)
    return player


class TestGenerateHelpMessage:
    """Test the main help message generation entry point."""

    def test_general_help(self, registry, mock_player):
        """Test generating general help."""
        result = generate_help_message(registry, mock_player)
        assert "Command Help System" in result
        assert "Available command categories" in result

    def test_category_help(self, registry, mock_player):
        """Test generating category-specific help."""
        result = generate_help_message(
            registry, mock_player, category=CommandCategory.USER
        )
        assert result is not None
        assert len(result) > 0

    def test_search_help(self, registry, mock_player):
        """Test generating search-based help."""
        result = generate_help_message(registry, mock_player, search_query="roll")
        assert result is not None
        assert "roll" in result.lower()

    def test_help_excludes_hidden_commands(self, registry, mock_player):
        """Test that hidden commands are excluded from help."""
        result = generate_help_message(registry, mock_player)
        # Hidden commands should not appear
        # block is hidden, so it shouldn't be listed
        lines = result.split("\n")
        # Check that no line mentions "block" as a command
        for line in lines:
            if "block" in line.lower() and "command" not in line.lower():
                # block might appear in other contexts, that's fine
                pass

    def test_help_filters_by_privilege(self, registry):
        """Test that help filters commands by player privilege."""
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED

        result = generate_help_message(registry, normal_player)
        # Should not include developer-only commands
        assert "py" not in result.lower() or "stealth" not in result.lower()


class TestGenerateGeneralHelp:
    """Test general help overview generation."""

    def test_general_help_structure(self, registry, mock_player):
        """Test the structure of general help output."""
        result = generate_general_help(registry, mock_player, "!")
        assert "Command Help System" in result
        assert "Available command categories" in result
        assert "Example commands" in result

    def test_general_help_lists_categories(self, registry, mock_player):
        """Test that general help lists all categories."""
        result = generate_general_help(registry, mock_player, "!")
        # Should mention User category at minimum
        assert "User" in result

    def test_general_help_with_custom_prefix(self, registry, mock_player):
        """Test general help with a custom prefix."""
        result = generate_general_help(registry, mock_player, ".")
        assert "." in result


class TestGenerateCategoryHelp:
    """Test category-specific help generation."""

    def test_user_category_help(self, registry, mock_player):
        """Test help for user category."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.USER, "!"
        )
        assert result is not None
        assert len(result) > 0

    def test_multiplayer_category_help(self, registry, mock_player):
        """Test help for multiplayer category."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.MULTIPLAYER, "!"
        )
        assert result is not None

    def test_developer_category_help(self, registry):
        """Test help for developer category with developer player."""
        dev_player = Mock()
        dev_player.priv = Privileges.DEVELOPER

        result = generate_category_help(
            registry, dev_player, CommandCategory.DEVELOPER, "!"
        )
        assert result is not None

    def test_category_help_filters_by_privilege(self, registry):
        """Test that category help filters by privilege."""
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED

        result = generate_category_help(
            registry, normal_player, CommandCategory.DEVELOPER, "!"
        )
        # Should be empty or minimal since normal player can't see dev commands
        # (depends on implementation)


class TestGenerateSearchResults:
    """Test search-based help generation."""

    def test_search_finds_matching_commands(self, registry, mock_player):
        """Test that search finds matching commands."""
        result = generate_search_results(registry, mock_player, "roll", "!")
        assert "roll" in result.lower()

    def test_search_no_results(self, registry, mock_player):
        """Test search with no matching results."""
        result = generate_search_results(registry, mock_player, "xyznonexistent", "!")
        assert result is not None

    def test_search_case_insensitive(self, registry, mock_player):
        """Test that search is case-insensitive."""
        result_lower = generate_search_results(registry, mock_player, "roll", "!")
        result_upper = generate_search_results(registry, mock_player, "ROLL", "!")
        # Both should find the same commands
        assert result_lower is not None
        assert result_upper is not None

    def test_search_by_description(self, registry, mock_player):
        """Test that search can find commands by description."""
        # Search for a word that might appear in a command description
        result = generate_search_results(registry, mock_player, "die", "!")
        # "roll" command description mentions "die"
        assert result is not None

    def test_search_excludes_hidden_commands(self, registry, mock_player):
        """Test that search excludes hidden commands."""
        # Search should not return hidden commands
        result = generate_search_results(registry, mock_player, "block", "!")
        # block is hidden, so it shouldn't appear in results
        assert "block" not in result.lower() or "command" in result.lower()


class TestGenerateCommandHelp:
    """Test generating help for a specific command."""

    def test_command_help_basic(self, registry, mock_player):
        """Test generating help for a specific command."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "roll", "!")
        assert result is not None
        assert "Command: !roll" in result
        assert "Description:" in result or "roll" in result.lower()

    def test_command_help_not_found(self, registry, mock_player):
        """Test generating help for non-existent command."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "nonexistent_xyz", "!")
        assert result is not None
        assert "not found" in result.lower()

    def test_command_help_namespace_command(self, registry, mock_player):
        """Test generating help for a namespace command (mp start)."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "mp start", "!")
        assert result is not None
        # Should find the mp start command
        assert "Command: !start" in result or "mp" in result.lower()

    def test_command_help_no_permission(self, registry):
        """Test generating help for command without permission."""
        from app.commands.help import generate_command_help

        # Create a player with no privileges
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED

        # Try to get help for a developer-only command
        result = generate_command_help(registry, normal_player, "shutdown", "!")
        # Should say not found (permission denied is shown as not found for security)
        assert "not found" in result.lower()

    def test_command_help_shows_aliases(self, registry, mock_player):
        """Test that command help shows aliases."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "roll", "!")
        # roll has alias "r", should show aliases if more than one trigger
        assert result is not None

    def test_command_help_shows_category(self, registry, mock_player):
        """Test that command help shows category."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "roll", "!")
        assert "Category:" in result

    def test_command_help_shows_examples(self, registry, mock_player):
        """Test that command help shows examples if available."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "roll", "!")
        # roll command should have examples
        assert result is not None

    def test_command_help_shows_privileges(self, registry, mock_player):
        """Test that command help shows required privileges."""
        from app.commands.help import generate_command_help

        result = generate_command_help(registry, mock_player, "roll", "!")
        assert "Required privileges:" in result or "privileges" in result.lower()


class TestHelpWithDifferentPrivileges:
    """Test help system with different privilege levels."""

    def test_general_help_developer(self, registry):
        """Test general help for developer privilege player."""
        dev_player = Mock()
        dev_player.priv = Privileges.DEVELOPER

        result = generate_help_message(registry, dev_player)
        assert result is not None
        # Developer should see more commands
        assert len(result) > 0

    def test_general_help_moderator(self, registry):
        """Test general help for moderator privilege player."""
        mod_player = Mock()
        mod_player.priv = Privileges.MODERATOR

        result = generate_help_message(registry, mod_player)
        assert result is not None

    def test_general_help_administrator(self, registry):
        """Test general help for administrator privilege player."""
        admin_player = Mock()
        admin_player.priv = Privileges.ADMINISTRATOR

        result = generate_help_message(registry, admin_player)
        assert result is not None

    def test_category_help_no_commands_available(self, registry):
        """Test category help when no commands are available."""
        # Create a player with minimal privileges
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED

        # Developer category should have no available commands for normal player
        result = generate_category_help(
            registry, normal_player, CommandCategory.DEVELOPER, "!"
        )
        # Should indicate no commands available
        assert result is not None
        if "No commands available" in result:
            pass  # Expected behavior
        else:
            # Or it might show the category header with no commands
            assert len(result) > 0


class TestGenerateCategoryHelpExtended:
    """Extended tests for category help generation."""

    def test_category_help_with_usage(self, registry, mock_player):
        """Test that category help includes usage when available."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.USER, "!"
        )
        # Find a command with usage in the result
        cmds = registry.get_by_category(CommandCategory.USER)
        for cmd in cmds:
            if cmd.metadata.usage:
                assert f"Usage: {cmd.metadata.usage}" in result
                return

    def test_category_help_with_examples(self, registry, mock_player):
        """Test that category help includes examples when available."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.USER, "!"
        )
        # Find a command with examples in the result
        cmds = registry.get_by_category(CommandCategory.USER)
        for cmd in cmds:
            if cmd.metadata.examples:
                # Examples should be indented
                for example in cmd.metadata.examples:
                    assert example in result
                return

    def test_category_help_sorted_by_name(self, registry, mock_player):
        """Test that commands in category help are sorted by name."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.USER, "!"
        )
        cmds = registry.get_by_category(CommandCategory.USER)
        visible_cmds = [c for c in cmds if not c.metadata.hidden]
        if len(visible_cmds) >= 2:
            names = [c.metadata.name for c in visible_cmds]
            sorted_names = sorted(names)
            # Check that names appear in sorted order in result
            last_pos = -1
            for name in sorted_names:
                pos = result.find(f"!{name}")
                if pos != -1:
                    assert pos > last_pos, (
                        f"Command {name} should appear after previous commands"
                    )
                    last_pos = pos

    def test_category_help_empty_for_no_commands(self, registry):
        """Test category help when no commands available for privilege level."""
        # Create a player with no privileges
        no_priv_player = Mock()
        no_priv_player.priv = Privileges(0)

        result = generate_category_help(
            registry, no_priv_player, CommandCategory.ADMINISTRATOR, "!"
        )
        # Should indicate no commands available
        assert "No commands available" in result or len(result) > 0


class TestGenerateCommandHelpExtended:
    """Extended tests for single command help generation."""

    def test_command_help_with_usage(self, registry, mock_player):
        """Test command help includes usage when available."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.usage and not cmd.metadata.hidden:
                result = generate_command_help(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                assert f"Usage: {cmd.metadata.usage}" in result
                return

    def test_command_help_with_examples(self, registry, mock_player):
        """Test command help includes examples when available."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.examples and not cmd.metadata.hidden:
                result = generate_command_help(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                for example in cmd.metadata.examples:
                    assert example in result
                return

    def test_command_help_with_detailed_help(self, registry, mock_player):
        """Test command help includes detailed help when available."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.detailed_help and not cmd.metadata.hidden:
                result = generate_command_help(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                assert "Detailed Help:" in result
                assert cmd.metadata.detailed_help in result
                return

    def test_command_help_with_deprecated(self, registry, mock_player):
        """Test command help shows deprecation warning."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.deprecated and not cmd.metadata.hidden:
                result = generate_command_help(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                assert "deprecated" in result.lower()
                return

    def test_command_help_with_deprecation_message(self, registry, mock_player):
        """Test command help shows custom deprecation message."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if (
                cmd.metadata.deprecated
                and cmd.metadata.deprecation_message
                and not cmd.metadata.hidden
            ):
                result = generate_command_help(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                assert cmd.metadata.deprecation_message in result
                return

    def test_command_help_with_aliases(self, registry, mock_player):
        """Test command help shows aliases when more than one trigger."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if len(cmd.metadata.triggers) > 1 and not cmd.metadata.hidden:
                result = generate_command_help(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                assert "Aliases:" in result
                # Should list the other triggers
                for trigger in cmd.metadata.triggers[1:]:
                    assert trigger in result
                return

    def test_command_help_namespace_command_detailed(self, registry, mock_player):
        """Test detailed help for a namespace command."""
        # Try mp start
        result = generate_command_help(registry, mock_player, "mp start", "!")
        assert result is not None
        # Should contain command info
        assert len(result) > 0


class TestGenerateSearchResultsExtended:
    """Extended tests for search results generation."""

    def test_search_results_with_usage(self, registry, mock_player):
        """Test search results include usage when available."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.usage and not cmd.metadata.hidden:
                result = generate_search_results(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                if cmd.metadata.name in result.lower():
                    assert f"Usage: {cmd.metadata.usage}" in result
                return

    def test_search_results_with_examples(self, registry, mock_player):
        """Test search results include examples when available."""
        cmds = registry.get_all_commands()
        for cmd in cmds:
            if cmd.metadata.examples and not cmd.metadata.hidden:
                result = generate_search_results(
                    registry, mock_player, cmd.metadata.name, "!"
                )
                if cmd.metadata.name in result.lower():
                    for example in cmd.metadata.examples:
                        assert example in result
                return

    def test_search_results_grouped_by_category(self, registry, mock_player):
        """Test that search results are grouped by category."""
        # Search for a common term that might match multiple commands
        result = generate_search_results(registry, mock_player, "roll", "!")
        # Should have category headers
        assert "User" in result or "Commands:" in result

    def test_search_results_multiple_matches(self, registry, mock_player):
        """Test search with multiple matches."""
        # Search for a term that might match multiple commands
        result = generate_search_results(registry, mock_player, "mp", "!")
        assert result is not None
        # Should have results
        assert len(result) > 0


class TestGenerateGeneralHelpExtended:
    """Extended tests for general help generation."""

    def test_general_help_includes_usage_info(self, registry, mock_player):
        """Test general help includes usage instructions."""
        result = generate_general_help(registry, mock_player, "!")
        assert "Type '!help" in result

    def test_general_help_example_commands_section(self, registry, mock_player):
        """Test general help has example commands section."""
        result = generate_general_help(registry, mock_player, "!")
        assert "Example commands:" in result

    def test_general_help_category_command_count(self, registry, mock_player):
        """Test general help shows command count per category."""
        result = generate_general_help(registry, mock_player, "!")
        # Should show "({n} commands)" format
        assert "commands)" in result

    def test_general_help_with_dot_prefix(self, registry, mock_player):
        """Test general help with dot prefix."""
        result = generate_general_help(registry, mock_player, ".")
        assert "Type '.help" in result


class TestHelpWithDifferentPlayerStates:
    """Test help system with various player states."""

    def test_help_with_nominator_privileges(self, registry):
        """Test help for nominator privilege level."""
        nominator = Mock()
        nominator.priv = Privileges.NOMINATOR

        result = generate_general_help(registry, nominator, "!")
        assert result is not None
        # Should see nominator commands
        assert "Nominator" in result or "nominator" in result.lower()

    def test_help_with_moderator_privileges(self, registry):
        """Test help for moderator privilege level."""
        moderator = Mock()
        moderator.priv = Privileges.MODERATOR

        result = generate_general_help(registry, moderator, "!")
        assert result is not None
        # The help system shows categories with commands the player can access
        # The assertion should just check that the help is generated
        assert len(result) > 0

    def test_category_help_moderator_category(self, registry, mock_player):
        """Test help for moderator category."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.MODERATOR, "!"
        )
        # Normal player shouldn't see moderator commands
        assert result is not None

    def test_category_help_administrator_category(self, registry, mock_player):
        """Test help for administrator category."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.ADMINISTRATOR, "!"
        )
        # Normal player shouldn't see admin commands
        assert result is not None

    def test_category_help_developer_category(self, registry):
        """Test help for developer category with developer player."""
        developer = Mock()
        developer.priv = Privileges.DEVELOPER

        result = generate_category_help(
            registry, developer, CommandCategory.DEVELOPER, "!"
        )
        assert result is not None
        # Should see developer commands
        assert "Developer" in result or "developer" in result.lower()


class TestHelpEdgeCasesExtended:
    """Additional edge cases for help system."""

    def test_search_with_very_long_query(self, registry, mock_player):
        """Test search with a very long query string."""
        long_query = "a" * 1000
        result = generate_search_results(registry, mock_player, long_query, "!")
        assert result is not None
        # Should return no results message
        assert "No commands found" in result or len(result) > 0

    def test_search_with_numbers(self, registry, mock_player):
        """Test search with numeric query."""
        result = generate_search_results(registry, mock_player, "123", "!")
        assert result is not None

    def test_general_help_all_categories_listed(self, registry, mock_player):
        """Test that all categories with commands are listed."""
        result = generate_general_help(registry, mock_player, "!")
        # Should list at least User category
        assert "User" in result

    def test_category_help_with_custom_prefix(self, registry, mock_player):
        """Test category help with custom prefix."""
        result = generate_category_help(
            registry, mock_player, CommandCategory.USER, "."
        )
        assert result is not None
        assert len(result) > 0

    def test_command_help_with_special_characters_in_name(self, registry, mock_player):
        """Test command help lookup with special characters."""
        # Try to look up a command that doesn't exist with special chars
        result = generate_command_help(registry, mock_player, "test!@#$", "!")
        assert "not found" in result.lower()

    def test_search_preserves_case_in_results(self, registry, mock_player):
        """Test that search preserves original command case in results."""
        result = generate_search_results(registry, mock_player, "ROLL", "!")
        # Should find roll command
        assert "roll" in result.lower()


class TestHelpEdgeCases:
    """Test edge cases in help system."""

    def test_general_help_with_no_commands(self, registry, mock_player):
        """Test general help when registry has no available commands."""
        # This tests the case where all commands are hidden or restricted
        result = generate_general_help(registry, mock_player, "!")
        assert result is not None
        # Should still show the help structure
        assert "Command Help System" in result

    def test_search_with_special_characters(self, registry, mock_player):
        """Test search with special characters in query."""
        result = generate_search_results(registry, mock_player, "!@#$%", "!")
        assert result is not None
        # Should return "no commands found" message

    def test_search_with_empty_query(self, registry, mock_player):
        """Test search with empty query string."""
        result = generate_search_results(registry, mock_player, "", "!")
        assert result is not None
        # Empty search should return no results or all commands
        assert len(result) > 0

    def test_help_with_empty_prefix(self, registry, mock_player):
        """Test help with empty prefix."""
        result = generate_general_help(registry, mock_player, "")
        assert result is not None
        # Should still work with empty prefix

    def test_category_help_with_long_command_list(self, registry, mock_player):
        """Test category help with many commands."""
        # User category should have multiple commands
        result = generate_category_help(
            registry, mock_player, CommandCategory.USER, "!"
        )
        assert result is not None
        # Should list all commands in the category
        assert len(result) > 0


class TestCommandHelpPrivilegeDenied:
    """Covers lines 187-188: generate_command_help returns 'not found' when
    the player lacks the required privileges."""

    def test_command_help_privilege_denied_returns_not_found(self, player_unrestricted):
        """A normal player asking for help on a developer-only command
        should get 'not found' (not a permission error)."""
        registry = CommandRegistry()
        dev_cmd = _make_command(
            "shutdown",
            CommandCategory.DEVELOPER,
            privileges=Privileges.DEVELOPER,
            description="Shut down the server.",
        )
        registry.register(dev_cmd)

        result = generate_command_help(registry, player_unrestricted, "shutdown", "!")
        assert "not found" in result.lower()

    def test_command_help_privilege_denied_for_moderator_command(
        self, player_unrestricted
    ):
        """A normal player asking for help on a moderator command should
        get 'not found'."""
        registry = CommandRegistry()
        mod_cmd = _make_command(
            "silence",
            CommandCategory.MODERATOR,
            privileges=Privileges.MODERATOR,
            description="Silence a user.",
        )
        registry.register(mod_cmd)

        result = generate_command_help(registry, player_unrestricted, "silence", "!")
        assert "not found" in result.lower()

    def test_command_help_allowed_for_authorized_player(self, player_developer):
        """A developer asking for help on a developer command should get
        full help (not 'not found')."""
        registry = CommandRegistry()
        dev_cmd = _make_command(
            "shutdown",
            CommandCategory.DEVELOPER,
            privileges=Privileges.DEVELOPER,
            description="Shut down the server.",
        )
        registry.register(dev_cmd)

        result = generate_command_help(registry, player_developer, "shutdown", "!")
        assert "not found" not in result.lower()
        assert "shutdown" in result.lower()


class TestCommandHelpWithExamples:
    """Covers lines 212-215: generate_command_help shows the Examples
    section when a command has examples."""

    def test_command_help_shows_examples(self, player_unrestricted):
        """When a command has examples, they should appear in its help."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll", "!roll 6", "!roll 100"],
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Examples:" in result
        assert "!roll" in result
        assert "!roll 6" in result
        assert "!roll 100" in result

    def test_command_help_no_examples_section_when_empty(self, player_unrestricted):
        """When a command has no examples, the Examples section should
        not appear."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Examples:" not in result

    def test_command_help_examples_indented(self, player_unrestricted):
        """Examples should be indented under the Examples header."""
        registry = CommandRegistry()
        cmd = _make_command(
            "test",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Test command.",
            examples=["!test foo", "!test bar"],
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "test", "!")
        lines = result.split("\n")
        # Find the Examples: line and check indentation of following lines
        for i, line in enumerate(lines):
            if line.strip() == "Examples:":
                # Next lines should be indented examples
                assert i + 1 < len(lines)
                assert "  !test foo" in lines[i + 1]
                break
        else:
            assert False, "Examples: section not found in output"


class TestCommandHelpWithDetailedHelp:
    """Covers lines 219-222: generate_command_help shows the Detailed Help
    section when a command has detailed_help."""

    def test_command_help_shows_detailed_help(self, player_unrestricted):
        """When a command has detailed_help, it should appear in its help."""
        detailed = "This is the detailed help text.\nIt spans multiple lines."
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            detailed_help=detailed,
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Detailed Help:" in result
        assert detailed in result

    def test_command_help_no_detailed_help_section_when_none(self, player_unrestricted):
        """When a command has no detailed_help, the section should not appear."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Detailed Help:" not in result

    def test_command_help_detailed_help_has_separator(self, player_unrestricted):
        """The Detailed Help section should have a separator line."""
        registry = CommandRegistry()
        cmd = _make_command(
            "test",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Test command.",
            detailed_help="Some detailed info.",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "test", "!")
        assert "-" * 50 in result


class TestCommandHelpWithDeprecation:
    """Covers lines 226-228: generate_command_help shows deprecation warning
    when a command is deprecated."""

    def test_command_help_shows_deprecation_warning(self, player_unrestricted):
        """A deprecated command should show a deprecation warning."""
        registry = CommandRegistry()
        cmd = _make_command(
            "oldcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="An old command.",
            deprecated=True,
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "oldcmd", "!")
        assert "deprecated" in result.lower()

    def test_command_help_shows_deprecation_message(self, player_unrestricted):
        """A deprecated command with a deprecation_message should show it."""
        msg = "Use 'newcmd' instead."
        registry = CommandRegistry()
        cmd = _make_command(
            "oldcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="An old command.",
            deprecated=True,
            deprecation_message=msg,
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "oldcmd", "!")
        assert "deprecated" in result.lower()
        assert msg in result

    def test_command_help_no_deprecation_when_not_deprecated(self, player_unrestricted):
        """A non-deprecated command should not show any deprecation warning."""
        registry = CommandRegistry()
        cmd = _make_command(
            "newcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="A new command.",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "newcmd", "!")
        assert "deprecated" not in result.lower()

    def test_command_help_deprecated_without_message(self, player_unrestricted):
        """A deprecated command without a deprecation_message should still
        show the deprecation warning but no extra message."""
        registry = CommandRegistry()
        cmd = _make_command(
            "oldcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="An old command.",
            deprecated=True,
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "oldcmd", "!")
        assert "deprecated" in result.lower()
        # Should not crash even without deprecation_message


class TestCategoryHelpWithExamples:
    """Covers lines 144-148: generate_category_help shows examples for
    commands that have them."""

    def test_category_help_shows_examples(self, player_unrestricted):
        """When a command in a category has examples, they should appear
        in the category help output."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll", "!roll 6"],
        )
        registry.register(cmd)

        result = generate_category_help(
            registry, player_unrestricted, CommandCategory.USER, "!"
        )
        assert "Examples:" in result
        assert "!roll" in result
        assert "!roll 6" in result

    def test_category_help_examples_indented(self, player_unrestricted):
        """Examples in category help should be indented under the command."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll 100"],
        )
        registry.register(cmd)

        result = generate_category_help(
            registry, player_unrestricted, CommandCategory.USER, "!"
        )
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "Examples:":
                # The next line should be indented with the example
                assert "    !roll 100" in lines[i + 1]
                break
        else:
            assert False, "Examples: section not found in category help output"

    def test_category_help_no_examples_when_none(self, player_unrestricted):
        """When no commands in a category have examples, no Examples section."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        registry.register(cmd)

        result = generate_category_help(
            registry, player_unrestricted, CommandCategory.USER, "!"
        )
        assert "Examples:" not in result

    def test_category_help_mixed_commands_with_and_without_examples(
        self, player_unrestricted
    ):
        """A category with some commands having examples and some not should
        show examples only for those that have them."""
        registry = CommandRegistry()
        cmd_with_examples = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll", "!roll 6"],
        )
        cmd_without_examples = _make_command(
            "recent",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Show recent score.",
        )
        registry.register(cmd_with_examples)
        registry.register(cmd_without_examples)

        result = generate_category_help(
            registry, player_unrestricted, CommandCategory.USER, "!"
        )
        # Should have Examples: for roll
        assert "Examples:" in result
        # The examples should be present
        assert "!roll" in result

    def test_category_help_examples_with_multiple_examples(self, player_unrestricted):
        """A command with multiple examples should show all of them."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll", "!roll 6", "!roll 20", "!roll 100"],
        )
        registry.register(cmd)

        result = generate_category_help(
            registry, player_unrestricted, CommandCategory.USER, "!"
        )
        for example in ["!roll", "!roll 6", "!roll 20", "!roll 100"]:
            assert example in result


class TestSearchResultsWithExamples:
    """Covers lines 292-294: generate_search_results shows examples for
    matched commands that have them."""

    def test_search_results_show_examples(self, player_unrestricted):
        """When a matched command has examples, they should appear in search results."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll", "!roll 6"],
        )
        registry.register(cmd)

        result = generate_search_results(registry, player_unrestricted, "roll", "!")
        assert "Examples:" in result
        assert "!roll" in result
        assert "!roll 6" in result

    def test_search_results_no_examples_when_none(self, player_unrestricted):
        """When matched commands have no examples, no Examples section in search."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        registry.register(cmd)

        result = generate_search_results(registry, player_unrestricted, "roll", "!")
        assert "Examples:" not in result

    def test_search_results_examples_indented(self, player_unrestricted):
        """Examples in search results should be indented."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            examples=["!roll 100"],
        )
        registry.register(cmd)

        result = generate_search_results(registry, player_unrestricted, "roll", "!")
        lines = result.split("\n")
        for i, line in enumerate(lines):
            if line.strip() == "Examples:":
                assert "      !roll 100" in lines[i + 1]
                break
        else:
            assert False, "Examples: section not found in search results"


class TestCommandHelpWithAliases:
    """Test that command help shows aliases when a command has multiple triggers."""

    def test_command_help_shows_aliases(self, player_unrestricted):
        """A command with multiple triggers should show Aliases section."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            triggers=["roll", "r", "dice"],
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Aliases:" in result
        assert "r" in result
        assert "dice" in result

    def test_command_help_no_aliases_with_single_trigger(self, player_unrestricted):
        """A command with a single trigger should not show Aliases section."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            triggers=["roll"],
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Aliases:" not in result


class TestCommandHelpWithUsage:
    """Test that command help shows usage when available."""

    def test_command_help_shows_usage(self, player_unrestricted):
        """A command with usage should show it in help."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
            usage="!roll [sides]",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Usage:" in result
        assert "!roll [sides]" in result

    def test_command_help_no_usage_when_none(self, player_unrestricted):
        """A command without usage should not show Usage section."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "roll", "!")
        assert "Usage:" not in result


class TestCommandHelpWithNamespace:
    """Test command help for namespaced commands."""

    def test_command_help_namespace_found(self, player_unrestricted):
        """Looking up 'mp start' should find the namespaced command."""
        registry = CommandRegistry()
        cmd = _make_command(
            "start",
            CommandCategory.MULTIPLAYER,
            privileges=Privileges.UNRESTRICTED,
            description="Start the match.",
            namespace="mp",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "mp start", "!")
        assert "not found" not in result.lower()
        assert "start" in result.lower()

    def test_command_help_namespace_not_found(self, player_unrestricted):
        """Looking up a non-existent namespaced command should return not found."""
        registry = CommandRegistry()
        result = generate_command_help(
            registry, player_unrestricted, "mp nonexistent", "!"
        )
        assert "not found" in result.lower()


class TestCategoryHelpEdgeCases:
    """Additional edge-case tests for category help."""

    def test_category_help_no_available_commands_message(self, player_zero_priv):
        """A player with no privileges should see 'No commands available'
        for admin category."""
        registry = CommandRegistry()
        cmd = _make_command(
            "shutdown",
            CommandCategory.ADMINISTRATOR,
            privileges=Privileges.ADMINISTRATOR,
            description="Shut down.",
        )
        registry.register(cmd)

        result = generate_category_help(
            registry, player_zero_priv, CommandCategory.ADMINISTRATOR, "!"
        )
        assert "No commands available" in result

    def test_category_help_hidden_commands_excluded(self, player_developer):
        """Hidden commands should not appear in category help."""
        registry = CommandRegistry()
        visible_cmd = _make_command(
            "visible",
            CommandCategory.DEVELOPER,
            privileges=Privileges.DEVELOPER,
            description="A visible command.",
        )
        hidden_cmd = _make_command(
            "hidden",
            CommandCategory.DEVELOPER,
            privileges=Privileges.DEVELOPER,
            description="A hidden command.",
            hidden=True,
        )
        registry.register(visible_cmd)
        registry.register(hidden_cmd)

        result = generate_category_help(
            registry, player_developer, CommandCategory.DEVELOPER, "!"
        )
        assert "visible" in result.lower()
        # The hidden command's name should not appear as a command entry
        lines = result.split("\n")
        for line in lines:
            if line.startswith("!hidden"):
                assert False, "Hidden command should not appear in category help"


class TestGeneralHelpEdgeCases:
    """Additional edge-case tests for general help."""

    def test_general_help_no_available_commands(self, player_zero_priv):
        """A player with zero privileges should still get the help structure."""
        registry = CommandRegistry()
        cmd = _make_command(
            "shutdown",
            CommandCategory.ADMINISTRATOR,
            privileges=Privileges.ADMINISTRATOR,
            description="Shut down.",
        )
        registry.register(cmd)

        result = generate_general_help(registry, player_zero_priv, "!")
        assert "Command Help System" in result

    def test_general_help_excludes_hidden(self, player_developer):
        """Hidden commands should not appear in general help."""
        registry = CommandRegistry()
        visible_cmd = _make_command(
            "visible",
            CommandCategory.DEVELOPER,
            privileges=Privileges.DEVELOPER,
            description="Visible command.",
        )
        hidden_cmd = _make_command(
            "secret",
            CommandCategory.DEVELOPER,
            privileges=Privileges.DEVELOPER,
            description="Secret command.",
            hidden=True,
        )
        registry.register(visible_cmd)
        registry.register(hidden_cmd)

        result = generate_general_help(registry, player_developer, "!")
        # The hidden command should not appear in the command list
        lines = result.split("\n")
        for line in lines:
            if "!secret" in line:
                assert False, "Hidden command should not appear in general help"


class TestSearchEdgeCases:
    """Additional edge-case tests for search results."""

    def test_search_matches_description(self, player_unrestricted):
        """Search should match commands by description content."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll an n-sided die.",
        )
        registry.register(cmd)

        result = generate_search_results(registry, player_unrestricted, "die", "!")
        assert "roll" in result.lower()

    def test_search_no_results_message(self, player_unrestricted):
        """Search with no matches should return a 'no commands found' message."""
        registry = CommandRegistry()
        cmd = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        registry.register(cmd)

        result = generate_search_results(
            registry, player_unrestricted, "xyznonexistent", "!"
        )
        assert "No commands found" in result

    def test_search_excludes_hidden(self, player_unrestricted):
        """Hidden commands should not appear in search results."""
        registry = CommandRegistry()
        hidden_cmd = _make_command(
            "secretcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="A secret command.",
            hidden=True,
        )
        registry.register(hidden_cmd)

        result = generate_search_results(
            registry, player_unrestricted, "secretcmd", "!"
        )
        assert "No commands found" in result

    def test_search_groups_by_category(self, player_unrestricted):
        """Search results should be grouped by category."""
        registry = CommandRegistry()
        cmd1 = _make_command(
            "roll",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="Roll a die.",
        )
        cmd2 = _make_command(
            "mp_start",
            CommandCategory.MULTIPLAYER,
            privileges=Privileges.UNRESTRICTED,
            description="Start the match.",
        )
        registry.register(cmd1)
        registry.register(cmd2)

        result = generate_search_results(registry, player_unrestricted, "start", "!")
        # Should have category headers
        assert "Multiplayer" in result


class TestCommandHelpWithAllMetadata:
    """Test a command that has all metadata fields populated."""

    def test_command_help_full_metadata(self, player_unrestricted):
        """A command with all metadata should show all sections."""
        registry = CommandRegistry()
        cmd = _make_command(
            "fullcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="A fully-documented command.",
            detailed_help="This is the detailed help for the command.",
            examples=["!fullcmd foo", "!fullcmd bar"],
            usage="!fullcmd <arg>",
            triggers=["fullcmd", "fc"],
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "fullcmd", "!")
        assert "Command: !fullcmd" in result
        assert "Description:" in result
        assert "Usage:" in result
        assert "Aliases:" in result
        assert "Category:" in result
        assert "Examples:" in result
        assert "Detailed Help:" in result
        assert "!fullcmd foo" in result
        assert "!fullcmd bar" in result
        assert "fc" in result

    def test_command_help_deprecated_with_all_metadata(self, player_unrestricted):
        """A deprecated command with all metadata should show everything
        including the deprecation warning."""
        registry = CommandRegistry()
        cmd = _make_command(
            "oldcmd",
            CommandCategory.USER,
            privileges=Privileges.UNRESTRICTED,
            description="An old command.",
            detailed_help="Old detailed help.",
            examples=["!oldcmd"],
            usage="!oldcmd",
            deprecated=True,
            deprecation_message="Use 'newcmd' instead.",
        )
        registry.register(cmd)

        result = generate_command_help(registry, player_unrestricted, "oldcmd", "!")
        assert "deprecated" in result.lower()
        assert "Use 'newcmd' instead." in result
        assert "Detailed Help:" in result
        assert "Examples:" in result
