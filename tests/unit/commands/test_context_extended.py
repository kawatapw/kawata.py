"""
Extended tests for command context helper methods.

Covers all Context helper methods and properties.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from app.commands.context import CommandResponse
from app.commands.context import Context
from app.constants.privileges import Privileges


@pytest.fixture
def mock_state():
    state = Mock()
    state.sessions = Mock()
    state.sessions.players = Mock()
    state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)
    return state


@pytest.fixture
def mock_player():
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    return player


@pytest.fixture
def mock_recipient():
    recipient = Mock()
    recipient.name = "#test"
    return recipient


@pytest.fixture
def basic_context(mock_player, mock_recipient, mock_state):
    """Create a basic context for testing."""
    return Context(
        player=mock_player,
        trigger="test",
        args=[],
        recipient=mock_recipient,
        raw_message="!test",
        database=Mock(),
        cache=Mock(),
        settings=Mock(),
        state=mock_state,
        command=None,
    )


class TestCommandResponse:
    """Test CommandResponse dataclass."""

    def test_basic_response(self):
        """Test creating a basic response."""
        resp = CommandResponse(resp="Hello")
        assert resp.resp == "Hello"
        assert resp.hidden is False
        assert resp.silence_duration is None

    def test_hidden_response(self):
        """Test creating a hidden response."""
        resp = CommandResponse(resp="Secret", hidden=True)
        assert resp.resp == "Secret"
        assert resp.hidden is True

    def test_response_with_silence(self):
        """Test creating a response with silence duration."""
        resp = CommandResponse(resp="Silenced", silence_duration=60.0)
        assert resp.resp == "Silenced"
        assert resp.silence_duration == 60.0


class TestContextGetPlayer:
    """Test Context.get_player method."""

    @pytest.mark.asyncio
    async def test_get_player_found(self, basic_context, mock_state):
        """Test getting a player that exists."""
        mock_player = Mock()
        mock_state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_player
        )

        result = await basic_context.get_player("SomePlayer")
        assert result is mock_player
        mock_state.sessions.players.from_cache_or_sql.assert_called_once_with(
            name="SomePlayer"
        )

    @pytest.mark.asyncio
    async def test_get_player_not_found(self, basic_context, mock_state):
        """Test getting a player that doesn't exist."""
        mock_state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)

        result = await basic_context.get_player("NonExistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_player_by_id_found(self, basic_context, mock_state):
        """Test getting a player by ID."""
        mock_player = Mock()
        mock_state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_player
        )

        result = await basic_context.get_player_by_id(123)
        assert result is mock_player
        mock_state.sessions.players.from_cache_or_sql.assert_called_once_with(id=123)

    @pytest.mark.asyncio
    async def test_get_player_by_id_not_found(self, basic_context, mock_state):
        """Test getting a player by ID that doesn't exist."""
        mock_state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)

        result = await basic_context.get_player_by_id(999)
        assert result is None


class TestContextReplyMethods:
    """Test Context reply, error, success, and usage_error methods."""

    def test_reply_basic(self, basic_context):
        """Test basic reply method."""
        response = basic_context.reply("Hello World")
        assert isinstance(response, CommandResponse)
        assert response.resp == "Hello World"
        assert response.hidden is False

    def test_reply_hidden(self, basic_context):
        """Test reply with hidden flag."""
        response = basic_context.reply("Secret", hidden=True)
        assert response.resp == "Secret"
        assert response.hidden is True

    def test_error(self, basic_context):
        """Test error method."""
        response = basic_context.error("Something went wrong")
        assert isinstance(response, CommandResponse)
        assert response.resp == "Error: Something went wrong"
        assert response.hidden is False

    def test_success(self, basic_context):
        """Test success method."""
        response = basic_context.success("Operation completed")
        assert isinstance(response, CommandResponse)
        assert response.resp == "Operation completed"
        assert response.hidden is False

    def test_usage_error_with_message(self, basic_context):
        """Test usage_error with additional message."""
        response = basic_context.usage_error("!command <arg>", "Missing argument")
        assert isinstance(response, CommandResponse)
        assert response.resp == "Invalid usage: Missing argument\nUsage: !command <arg>"

    def test_usage_error_without_message(self, basic_context):
        """Test usage_error without additional message."""
        response = basic_context.usage_error("!command <arg>")
        assert isinstance(response, CommandResponse)
        assert response.resp == "Usage: !command <arg>"


class TestContextProperties:
    """Test Context properties has_args and arg_count."""

    def test_has_args_true(self, basic_context):
        """Test has_args when args are present."""
        basic_context.args = ["arg1", "arg2"]
        assert basic_context.has_args is True

    def test_has_args_false(self, basic_context):
        """Test has_args when no args."""
        basic_context.args = []
        assert basic_context.has_args is False

    def test_arg_count(self, basic_context):
        """Test arg_count property."""
        basic_context.args = ["a", "b", "c"]
        assert basic_context.arg_count == 3

    def test_arg_count_empty(self, basic_context):
        """Test arg_count with empty args."""
        basic_context.args = []
        assert basic_context.arg_count == 0


class TestContextGetArg:
    """Test Context.get_arg method."""

    def test_get_arg_valid_index(self, basic_context):
        """Test getting argument at valid index."""
        basic_context.args = ["first", "second", "third"]
        assert basic_context.get_arg(0) == "first"
        assert basic_context.get_arg(1) == "second"
        assert basic_context.get_arg(2) == "third"

    def test_get_arg_invalid_index(self, basic_context):
        """Test getting argument at invalid index returns None."""
        basic_context.args = ["first"]
        assert basic_context.get_arg(5) is None

    def test_get_arg_with_default(self, basic_context):
        """Test getting argument with default value."""
        basic_context.args = ["first"]
        assert basic_context.get_arg(0) == "first"
        assert basic_context.get_arg(1, default="default_val") == "default_val"
        assert basic_context.get_arg(0, default="not_used") == "first"

    def test_get_arg_empty_args(self, basic_context):
        """Test get_arg with empty args list."""
        basic_context.args = []
        assert basic_context.get_arg(0) is None
        assert basic_context.get_arg(0, default="fallback") == "fallback"


class TestContextJoinArgs:
    """Test Context.join_args method."""

    def test_join_args_all(self, basic_context):
        """Test joining all arguments."""
        basic_context.args = ["one", "two", "three"]
        assert basic_context.join_args() == "one two three"

    def test_join_args_from_index(self, basic_context):
        """Test joining arguments from a start index."""
        basic_context.args = ["one", "two", "three", "four"]
        assert basic_context.join_args(start=1) == "two three four"
        assert basic_context.join_args(start=2) == "three four"

    def test_join_args_with_range(self, basic_context):
        """Test joining arguments with start and end."""
        basic_context.args = ["one", "two", "three", "four"]
        assert basic_context.join_args(start=0, end=2) == "one two"
        assert basic_context.join_args(start=1, end=3) == "two three"

    def test_join_args_custom_separator(self, basic_context):
        """Test joining with custom separator."""
        basic_context.args = ["one", "two", "three"]
        assert basic_context.join_args(sep=", ") == "one, two, three"
        assert basic_context.join_args(sep="-") == "one-two-three"

    def test_join_args_empty(self, basic_context):
        """Test joining empty args."""
        basic_context.args = []
        assert basic_context.join_args() == ""

    def test_join_args_single(self, basic_context):
        """Test joining single arg."""
        basic_context.args = ["only"]
        assert basic_context.join_args() == "only"

    def test_join_args_end_none(self, basic_context):
        """Test join_args with end=None (should join to end)."""
        basic_context.args = ["one", "two", "three", "four"]
        assert basic_context.join_args(start=1, end=None) == "two three four"


class TestContextParsedDurations:
    """Test Context parsed_durations field."""

    def test_parsed_durations_initial_none(self, basic_context):
        """Test that parsed_durations is initially None."""
        assert basic_context.parsed_durations is None

    def test_parsed_durations_set(self, basic_context):
        """Test setting parsed_durations."""
        basic_context.parsed_durations = {0: 600.0, 1: 300.0}
        assert basic_context.parsed_durations == {0: 600.0, 1: 300.0}
        assert basic_context.parsed_durations[0] == 600.0


class TestContextCommandField:
    """Test Context command field."""

    def test_command_initial_none(self, basic_context):
        """Test that command is initially None."""
        assert basic_context.command is None

    def test_command_set(self, basic_context):
        """Test setting command field."""
        mock_cmd = Mock()
        basic_context.command = mock_cmd
        assert basic_context.command is mock_cmd
