"""
Tests for the command context module.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from app.commands.base import Command
from app.commands.base import CommandCategory
from app.commands.base import CommandMetadata
from app.commands.context import CommandResponse
from app.commands.context import Context


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = 1
    player.is_online = True
    return player


@pytest.fixture
def mock_recipient():
    """Create a mock recipient."""
    recipient = Mock()
    recipient.name = "TestChannel"
    return recipient


@pytest.fixture
def mock_database():
    """Create a mock database."""
    database = AsyncMock()
    return database


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock()
    return cache


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.COMMAND_PREFIX = "!"
    settings.DOMAIN = "osu.test"
    return settings


@pytest.fixture
def mock_state():
    """Create mock state."""
    state = Mock()
    state.sessions = Mock()
    state.sessions.players = Mock()
    state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)
    state.sessions.bot = Mock()
    return state


@pytest.fixture
def mock_command():
    """Create a mock command."""
    metadata = CommandMetadata(
        name="test",
        triggers=["test"],
        category=CommandCategory.USER,
    )
    return Command(
        metadata=metadata,
        callback=AsyncMock(return_value="test result"),
        privileges=1,
    )


@pytest.fixture
def context(
    mock_player,
    mock_recipient,
    mock_database,
    mock_cache,
    mock_settings,
    mock_state,
    mock_command,
):
    """Create a complete context for testing."""
    return Context(
        player=mock_player,
        trigger="test",
        args=["arg1", "arg2"],
        recipient=mock_recipient,
        raw_message="!test arg1 arg2",
        database=mock_database,
        cache=mock_cache,
        settings=mock_settings,
        state=mock_state,
        command=mock_command,
    )


class TestContextCreation:
    """Test context creation and attributes."""

    def test_context_creation(self, context):
        """Test that context is created with all required attributes."""
        assert context.player.name == "TestPlayer"
        assert context.trigger == "test"
        assert context.args == ["arg1", "arg2"]
        assert context.recipient.name == "TestChannel"
        assert context.raw_message == "!test arg1 arg2"
        assert context.database is not None
        assert context.cache is not None
        assert context.settings is not None
        assert context.state is not None
        assert context.command is not None

    def test_context_without_optional_fields(self, mock_player, mock_recipient):
        """Test context creation without optional fields."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=mock_recipient,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=Mock(),
        )

        assert context.args == []
        assert context.raw_message == "!test"


class TestContextHelperMethods:
    """Test context helper methods."""

    @pytest.mark.asyncio
    async def test_get_player(self, context, mock_state):
        """Test getting a player by name."""
        mock_player = Mock()
        mock_player.name = "TargetPlayer"
        mock_state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_player
        )

        result = await context.get_player("TargetPlayer")

        assert result == mock_player
        mock_state.sessions.players.from_cache_or_sql.assert_called_once_with(
            name="TargetPlayer"
        )

    @pytest.mark.asyncio
    async def test_get_player_not_found(self, context, mock_state):
        """Test getting a player that doesn't exist."""
        mock_state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)

        result = await context.get_player("NonExistent")

        assert result is None

    def test_reply(self, context):
        """Test creating a response with reply method."""
        response = context.reply("Test response")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Test response"
        assert response.hidden is False

    def test_reply_hidden(self, context):
        """Test creating a hidden response."""
        response = context.reply("Hidden response", hidden=True)

        assert isinstance(response, CommandResponse)
        assert response.resp == "Hidden response"
        assert response.hidden is True


class TestCommandResponse:
    """Test CommandResponse dataclass."""

    def test_command_response_creation(self):
        """Test creating a command response."""
        response = CommandResponse(resp="Test response")

        assert response.resp == "Test response"
        assert response.hidden is False
        assert response.silence_duration is None

    def test_command_response_with_hidden(self):
        """Test creating a hidden command response."""
        response = CommandResponse(resp="Hidden", hidden=True)

        assert response.resp == "Hidden"
        assert response.hidden is True

    def test_command_response_with_silence_duration(self):
        """Test creating a command response with silence duration."""
        response = CommandResponse(resp="Silenced", silence_duration=60)

        assert response.resp == "Silenced"
        assert response.silence_duration == 60


class TestContextEdgeCases:
    """Test edge cases for context."""

    def test_context_with_empty_args(self, mock_player, mock_recipient, mock_command):
        """Test context with empty args list."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=mock_recipient,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.args == []
        assert len(context.args) == 0

    def test_context_with_many_args(self, mock_player, mock_recipient, mock_command):
        """Test context with many arguments."""
        many_args = [f"arg{i}" for i in range(100)]
        context = Context(
            player=mock_player,
            trigger="test",
            args=many_args,
            recipient=mock_recipient,
            raw_message="!test " + " ".join(many_args),
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert len(context.args) == 100
        assert context.args[0] == "arg0"
        assert context.args[99] == "arg99"

    def test_context_with_special_characters_in_args(
        self, mock_player, mock_recipient, mock_command
    ):
        """Test context with special characters in arguments."""
        special_args = ["test@example.com", "user_name", "123-456-7890"]
        context = Context(
            player=mock_player,
            trigger="test",
            args=special_args,
            recipient=mock_recipient,
            raw_message="!test " + " ".join(special_args),
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.args == special_args


class TestContextWithDifferentRecipients:
    """Test context with different recipient types."""

    def test_context_with_channel_recipient(self, mock_player, mock_command):
        """Test context with a channel as recipient."""
        channel = Mock()
        channel.name = "#test"

        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=channel,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.recipient == channel
        assert context.recipient.name == "#test"

    def test_context_with_player_recipient(self, mock_player, mock_command):
        """Test context with a player as recipient."""
        recipient_player = Mock()
        recipient_player.name = "OtherPlayer"

        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=recipient_player,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.recipient == recipient_player
        assert context.recipient.name == "OtherPlayer"


class TestContextWithParsedDurations:
    """Test context with parsed durations."""

    def test_parsed_durations_initialization(self, context):
        """Test that parsed_durations is initially None."""
        assert context.parsed_durations is None

    def test_parsed_durations_assignment(self, context):
        """Test assigning parsed durations."""
        context.parsed_durations = {0: 600, 1: 300}

        assert context.parsed_durations == {0: 600, 1: 300}
        assert 0 in context.parsed_durations
        assert 1 in context.parsed_durations


class TestContextErrorMethod:
    """Test the error() helper method."""

    def test_error_creates_error_response(self, context):
        """Test that error() creates a CommandResponse with error prefix."""
        response = context.error("Something went wrong")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Error: Something went wrong"
        assert response.hidden is False

    def test_error_with_empty_message(self, context):
        """Test error() with empty message."""
        response = context.error("")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Error: "


class TestContextSuccessMethod:
    """Test the success() helper method."""

    def test_success_creates_success_response(self, context):
        """Test that success() creates a CommandResponse."""
        response = context.success("Operation completed")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Operation completed"
        assert response.hidden is False

    def test_success_with_empty_message(self, context):
        """Test success() with empty message."""
        response = context.success("")

        assert isinstance(response, CommandResponse)
        assert response.resp == ""


class TestContextUsageErrorMethod:
    """Test the usage_error() helper method."""

    def test_usage_error_with_message(self, context):
        """Test usage_error() with both usage and message."""
        response = context.usage_error("!command <arg>", "Missing argument")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Invalid usage: Missing argument\nUsage: !command <arg>"

    def test_usage_error_without_message(self, context):
        """Test usage_error() with only usage."""
        response = context.usage_error("!command <arg>")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Usage: !command <arg>"

    def test_usage_error_with_empty_usage(self, context):
        """Test usage_error() with empty usage string."""
        response = context.usage_error("")

        assert isinstance(response, CommandResponse)
        assert response.resp == "Usage: "


class TestContextHasArgsProperty:
    """Test the has_args property."""

    def test_has_args_with_empty_args(self, mock_player, mock_recipient, mock_command):
        """Test has_args returns False when args is empty."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=mock_recipient,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.has_args is False

    def test_has_args_with_args(self, context):
        """Test has_args returns True when args exist."""
        assert context.has_args is True

    def test_has_args_with_single_arg(self, mock_player, mock_recipient, mock_command):
        """Test has_args with single argument."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=["single"],
            recipient=mock_recipient,
            raw_message="!test single",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.has_args is True


class TestContextArgCountProperty:
    """Test the arg_count property."""

    def test_arg_count_with_empty_args(self, mock_player, mock_recipient, mock_command):
        """Test arg_count returns 0 when args is empty."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=mock_recipient,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.arg_count == 0

    def test_arg_count_with_args(self, context):
        """Test arg_count returns correct count."""
        assert context.arg_count == 2

    def test_arg_count_with_many_args(self, mock_player, mock_recipient, mock_command):
        """Test arg_count with many arguments."""
        many_args = [f"arg{i}" for i in range(50)]
        context = Context(
            player=mock_player,
            trigger="test",
            args=many_args,
            recipient=mock_recipient,
            raw_message="!test " + " ".join(many_args),
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.arg_count == 50


class TestContextGetArgMethod:
    """Test the get_arg() method."""

    def test_get_arg_valid_index(self, context):
        """Test get_arg() with valid index."""
        assert context.get_arg(0) == "arg1"
        assert context.get_arg(1) == "arg2"

    def test_get_arg_out_of_bounds(self, context):
        """Test get_arg() with out of bounds index."""
        assert context.get_arg(5) is None
        assert context.get_arg(100) is None

    def test_get_arg_with_default(self, context):
        """Test get_arg() with default value."""
        assert context.get_arg(5, "default") == "default"
        assert context.get_arg(0, "default") == "arg1"  # Should return actual value

    def test_get_arg_negative_index(self, context):
        """Test get_arg() with negative index."""
        # Negative indices work like Python lists
        assert context.get_arg(-1) == "arg2"  # Last element
        assert context.get_arg(-2) == "arg1"  # Second to last


class TestContextJoinArgsMethod:
    """Test the join_args() method."""

    def test_join_args_all(self, context):
        """Test join_args() with all arguments."""
        assert context.join_args() == "arg1 arg2"

    def test_join_args_from_index(self, context):
        """Test join_args() starting from specific index."""
        assert context.join_args(1) == "arg2"
        assert context.join_args(0) == "arg1 arg2"

    def test_join_args_with_range(self, context):
        """Test join_args() with start and end."""
        many_args = ["a", "b", "c", "d", "e"]
        # Create new context with many args
        mock_player = Mock()
        mock_player.name = "Test"
        mock_player.id = 1
        mock_player.priv = 1
        mock_command = Mock()
        mock_context = Context(
            player=mock_player,
            trigger="test",
            args=many_args,
            recipient=Mock(),
            raw_message="!test a b c d e",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert mock_context.join_args(1, 3) == "b c"
        assert mock_context.join_args(0, 2) == "a b"

    def test_join_args_with_custom_separator(self, context):
        """Test join_args() with custom separator."""
        assert context.join_args(sep=", ") == "arg1, arg2"
        assert context.join_args(sep="-") == "arg1-arg2"

    def test_join_args_empty_context(self, mock_player, mock_recipient, mock_command):
        """Test join_args() with empty args."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=[],
            recipient=mock_recipient,
            raw_message="!test",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.join_args() == ""
        assert context.join_args(0, 5) == ""

    def test_join_args_single_arg(self, mock_player, mock_recipient, mock_command):
        """Test join_args() with single argument."""
        context = Context(
            player=mock_player,
            trigger="test",
            args=["single"],
            recipient=mock_recipient,
            raw_message="!test single",
            database=Mock(),
            cache=Mock(),
            settings=Mock(),
            state=Mock(),
            command=mock_command,
        )

        assert context.join_args() == "single"
        assert context.join_args(0, 1) == "single"
