"""
Extended tests for the command context module.

Covers Context dataclass construction, helper methods, and CommandResponse.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from app.commands.context import CommandResponse
from app.commands.context import Context


class TestCommandResponse:
    """Test CommandResponse dataclass."""

    def test_default_hidden(self):
        """Test that hidden defaults to False."""
        resp = CommandResponse(resp="test")
        assert resp.hidden is False
        assert resp.resp == "test"

    def test_explicit_hidden(self):
        """Test setting hidden to True."""
        resp = CommandResponse(resp="test", hidden=True)
        assert resp.hidden is True

    def test_none_response(self):
        """Test None response."""
        resp = CommandResponse(resp=None)
        assert resp.resp is None
        assert resp.hidden is False


class TestContext:
    """Test Context dataclass and helper methods."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        player = Mock()
        player.name = "TestPlayer"
        player.id = 1
        return player

    @pytest.fixture
    def mock_recipient(self):
        """Create a mock recipient."""
        recipient = Mock()
        recipient.name = "#test"
        return recipient

    @pytest.fixture
    def context(self, mock_player, mock_recipient):
        """Create a test context."""
        state = Mock()
        state.sessions = Mock()
        state.sessions.players = Mock()
        state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)

        return Context(
            player=mock_player,
            trigger="test",
            args=["arg1", "arg2"],
            recipient=mock_recipient,
            raw_message="!test arg1 arg2",
            database=AsyncMock(),
            cache=Mock(),
            settings=Mock(),
            state=state,
        )

    def test_context_creation(self, context):
        """Test basic context creation."""
        assert context.player.name == "TestPlayer"
        assert context.trigger == "test"
        assert context.args == ["arg1", "arg2"]
        assert context.raw_message == "!test arg1 arg2"
        assert context.command is None
        assert context.parsed_durations is None

    def test_context_with_command(self, context):
        """Test context with command metadata."""
        cmd = Mock()
        context.command = cmd
        assert context.command is cmd

    def test_context_with_parsed_durations(self, context):
        """Test context with parsed durations."""
        context.parsed_durations = {0: 60.0}
        assert context.parsed_durations[0] == 60.0

    @pytest.mark.asyncio
    async def test_get_player(self, context):
        """Test get_player helper method."""
        target = Mock()
        target.name = "Target"
        context.state.sessions.players.from_cache_or_sql = AsyncMock(return_value=target)

        result = await context.get_player("Target")
        assert result is target
        context.state.sessions.players.from_cache_or_sql.assert_called_once_with(name="Target")

    @pytest.mark.asyncio
    async def test_get_player_not_found(self, context):
        """Test get_player when player not found."""
        context.state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)

        result = await context.get_player("NonExistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_player_by_id(self, context):
        """Test get_player_by_id helper method."""
        target = Mock()
        target.id = 42
        context.state.sessions.players.from_cache_or_sql = AsyncMock(return_value=target)

        result = await context.get_player_by_id(42)
        assert result is target
        context.state.sessions.players.from_cache_or_sql.assert_called_once_with(id=42)

    @pytest.mark.asyncio
    async def test_get_player_by_id_not_found(self, context):
        """Test get_player_by_id when player not found."""
        context.state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)

        result = await context.get_player_by_id(999)
        assert result is None

    def test_reply(self, context):
        """Test reply helper method."""
        resp = context.reply("Hello world")
        assert resp.resp == "Hello world"
        assert resp.hidden is False

    def test_reply_hidden(self, context):
        """Test reply with hidden=True."""
        resp = context.reply("Secret message", hidden=True)
        assert resp.resp == "Secret message"
        assert resp.hidden is True
