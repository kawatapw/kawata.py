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
