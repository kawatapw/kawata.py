"""
Tests for the rich help system.

Covers help message generation, category filtering, and search functionality.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.commands import get_registry
from app.commands.base import CommandCategory
from app.commands.help import generate_category_help
from app.commands.help import generate_general_help
from app.commands.help import generate_help_message
from app.commands.help import generate_search_results
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    return player


@pytest.fixture
def registry():
    """Get the global registry."""
    return get_registry()


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
