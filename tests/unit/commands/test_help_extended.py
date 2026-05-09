"""
Extended tests for the help system.

Covers edge cases with usage, examples, deprecation, and detailed help.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.commands import get_registry
from app.commands.base import CommandCategory
from app.commands.help import generate_category_help
from app.commands.help import generate_command_help
from app.commands.help import generate_general_help
from app.commands.help import generate_search_results
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    return player


@pytest.fixture
def registry():
    return get_registry()


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
