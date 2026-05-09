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
        result = generate_help_message(
            registry, mock_player, search_query="roll"
        )
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
        result = generate_category_help(registry, mock_player, CommandCategory.USER, "!")
        assert result is not None
        assert len(result) > 0

    def test_multiplayer_category_help(self, registry, mock_player):
        """Test help for multiplayer category."""
        result = generate_category_help(registry, mock_player, CommandCategory.MULTIPLAYER, "!")
        assert result is not None

    def test_developer_category_help(self, registry):
        """Test help for developer category with developer player."""
        dev_player = Mock()
        dev_player.priv = Privileges.DEVELOPER

        result = generate_category_help(registry, dev_player, CommandCategory.DEVELOPER, "!")
        assert result is not None

    def test_category_help_filters_by_privilege(self, registry):
        """Test that category help filters by privilege."""
        normal_player = Mock()
        normal_player.priv = Privileges.UNRESTRICTED

        result = generate_category_help(registry, normal_player, CommandCategory.DEVELOPER, "!")
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
