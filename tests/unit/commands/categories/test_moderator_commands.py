"""
Tests for moderator commands.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.commands.categories.moderator import (
    SHORTHAND_REASONS,
    addnote,
    notes,
    silence,
    unsilence,
)
from app.commands.context import Context
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.MODERATOR
    player.is_online = True
    return player


@pytest.fixture
def mock_target_player():
    """Create a mock target player."""
    target = Mock()
    target.name = "TargetPlayer"
    target.id = 2
    target.priv = Privileges.UNRESTRICTED
    target.is_online = True
    target.silenced = False
    target.restricted = False
    target.__str__ = Mock(return_value="TargetPlayer")
    target.silence = AsyncMock()
    target.unsilence = AsyncMock()
    return target


@pytest.fixture
def mock_context(mock_player):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.args = []
    ctx.state = Mock()
    ctx.state.sessions = Mock()
    ctx.state.services = Mock()
    ctx.state.services.database = Mock()
    return ctx


class TestNotesCommand:
    """Test notes command."""

    @pytest.mark.asyncio
    async def test_notes_invalid_syntax(self, mock_context):
        """Test notes command with invalid syntax."""
        mock_context.args = ["player"]

        result = await notes.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result
        assert "!notes <name> <days_back>" in result

    @pytest.mark.asyncio
    async def test_notes_player_not_found(self, mock_context):
        """Test notes command when player not found."""
        mock_context.args = ["nonexistent", "7"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await notes.callback(mock_context)

        assert result is not None
        assert '"nonexistent" not found.' in result

    @pytest.mark.asyncio
    async def test_notes_too_many_days(self, mock_context, mock_target_player):
        """Test notes command with too many days."""
        mock_context.args = ["TargetPlayer", "400"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await notes.callback(mock_context)

        assert result is not None
        assert "Please contact a developer" in result

    @pytest.mark.asyncio
    async def test_notes_zero_days(self, mock_context, mock_target_player):
        """Test notes command with zero days."""
        mock_context.args = ["TargetPlayer", "0"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await notes.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_notes_no_results(self, mock_context, mock_target_player):
        """Test notes command when no notes found."""
        mock_context.args = ["TargetPlayer", "7"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )
        mock_context.state.services.database.fetch_all = AsyncMock(return_value=[])

        result = await notes.callback(mock_context)

        assert result is not None
        assert "No notes found on TargetPlayer" in result

    @pytest.mark.asyncio
    async def test_notes_with_results(self, mock_context, mock_target_player):
        """Test notes command with results."""
        mock_context.args = ["TargetPlayer", "7"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        # Mock database results
        mock_logger = Mock()
        mock_logger.name = "ModeratorName"

        mock_context.state.services.database.fetch_all = AsyncMock(
            return_value=[
                {
                    "action": "silence",
                    "reason": "spamming",
                    "time": "2024-01-01 12:00:00",
                    "mod": 3,
                }
            ]
        )

        # Mock the second from_cache_or_sql call for the moderator
        with patch.object(
            mock_context.state.sessions.players,
            "from_cache_or_sql",
            AsyncMock(return_value=mock_logger),
        ):
            result = await notes.callback(mock_context)

        assert result is not None
        assert "ModeratorName" in result
        assert "spamming" in result


class TestAddnoteCommand:
    """Test addnote command."""

    @pytest.mark.asyncio
    async def test_addnote_invalid_syntax(self, mock_context):
        """Test addnote command with invalid syntax."""
        mock_context.args = ["player"]

        result = await addnote.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result
        assert "!addnote <name> <note ...>" in result

    @pytest.mark.asyncio
    async def test_addnote_player_not_found(self, mock_context):
        """Test addnote command when player not found."""
        mock_context.args = ["nonexistent", "test", "note"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await addnote.callback(mock_context)

        assert result is not None
        assert '"nonexistent" not found.' in result

    @pytest.mark.asyncio
    async def test_addnote_success(self, mock_context, mock_target_player):
        """Test addnote command success."""
        mock_context.args = ["TargetPlayer", "test", "note"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        with patch("app.commands.categories.moderator.logs_repo.create", AsyncMock()):
            result = await addnote.callback(mock_context)

        assert result is not None
        assert "Added note to TargetPlayer." in result


class TestSilenceCommand:
    """Test silence command."""

    @pytest.mark.asyncio
    async def test_silence_invalid_syntax(self, mock_context):
        """Test silence command with invalid syntax."""
        mock_context.args = ["player"]

        result = await silence.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result
        assert "!silence <name> <duration> <reason>" in result

    @pytest.mark.asyncio
    async def test_silence_player_not_found(self, mock_context):
        """Test silence command when player not found."""
        mock_context.args = ["nonexistent", "10m", "spamming"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await silence.callback(mock_context)

        assert result is not None
        assert '"nonexistent" not found.' in result

    @pytest.mark.asyncio
    async def test_silence_staff_member_as_non_developer(
        self, mock_context, mock_target_player
    ):
        """Test silence command on staff member as non-developer."""
        mock_target_player.priv = Privileges.MODERATOR
        mock_context.args = ["TargetPlayer", "10m", "spamming"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await silence.callback(mock_context)

        assert result is not None
        assert "Only developers can manage staff members." in result

    @pytest.mark.asyncio
    async def test_silence_invalid_duration(self, mock_context, mock_target_player):
        """Test silence command with invalid duration."""
        mock_context.args = ["TargetPlayer", "invalid", "spamming"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await silence.callback(mock_context)

        assert result is not None
        assert "Invalid timespan." in result

    @pytest.mark.asyncio
    async def test_silence_with_shorthand_reason(
        self, mock_context, mock_target_player
    ):
        """Test silence command with shorthand reason."""
        mock_context.args = ["TargetPlayer", "10m", "aa"]
        mock_target_player.silence = AsyncMock()
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await silence.callback(mock_context)

        assert result is not None
        assert "TargetPlayer was silenced." in result
        # Verify shorthand was expanded
        mock_target_player.silence.assert_called_once()
        call_args = mock_target_player.silence.call_args
        assert call_args[0][2] == SHORTHAND_REASONS["aa"]

    @pytest.mark.asyncio
    async def test_silence_success(self, mock_context, mock_target_player):
        """Test silence command success."""
        mock_context.args = ["TargetPlayer", "10m", "spamming"]
        mock_target_player.silence = AsyncMock()
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await silence.callback(mock_context)

        assert result is not None
        assert "TargetPlayer was silenced." in result
        mock_target_player.silence.assert_called_once()


class TestUnsilenceCommand:
    """Test unsilence command."""

    @pytest.mark.asyncio
    async def test_unsilence_invalid_syntax(self, mock_context):
        """Test unsilence command with invalid syntax."""
        mock_context.args = ["player"]

        result = await unsilence.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result
        assert "!unsilence <name> <reason>" in result

    @pytest.mark.asyncio
    async def test_unsilence_player_not_found(self, mock_context):
        """Test unsilence command when player not found."""
        mock_context.args = ["nonexistent", "reason"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await unsilence.callback(mock_context)

        assert result is not None
        assert '"nonexistent" not found.' in result

    @pytest.mark.asyncio
    async def test_unsilence_not_silenced(self, mock_context, mock_target_player):
        """Test unsilence command on player who is not silenced."""
        mock_target_player.silenced = False
        mock_context.args = ["TargetPlayer", "reason"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await unsilence.callback(mock_context)

        assert result is not None
        assert "TargetPlayer is not silenced." in result

    @pytest.mark.asyncio
    async def test_unsilence_staff_member_as_non_developer(
        self, mock_context, mock_target_player
    ):
        """Test unsilence command on staff member as non-developer."""
        mock_target_player.silenced = True
        mock_target_player.priv = Privileges.MODERATOR
        mock_context.args = ["TargetPlayer", "reason"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await unsilence.callback(mock_context)

        assert result is not None
        assert "Only developers can manage staff members." in result

    @pytest.mark.asyncio
    async def test_unsilence_success(self, mock_context, mock_target_player):
        """Test unsilence command success."""
        mock_target_player.silenced = True
        mock_target_player.unsilence = AsyncMock()
        mock_context.args = ["TargetPlayer", "reason"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await unsilence.callback(mock_context)

        assert result is not None
        assert "TargetPlayer was unsilenced." in result
        mock_target_player.unsilence.assert_called_once()


class TestShorthandReasons:
    """Test shorthand reasons mapping."""

    def test_shorthand_reasons_exist(self):
        """Test that all shorthand reasons are defined."""
        assert "aa" in SHORTHAND_REASONS
        assert "cc" in SHORTHAND_REASONS
        assert "3p" in SHORTHAND_REASONS
        assert "rx" in SHORTHAND_REASONS
        assert "tw" in SHORTHAND_REASONS
        assert "au" in SHORTHAND_REASONS

    def test_shorthand_reasons_values(self):
        """Test shorthand reasons have correct values."""
        assert SHORTHAND_REASONS["aa"] == "having their appeal accepted"
        assert SHORTHAND_REASONS["cc"] == "using a modified osu! client"
        assert SHORTHAND_REASONS["3p"] == "using 3rd party programs"
        assert SHORTHAND_REASONS["rx"] == "using 3rd party programs (relax)"
        assert SHORTHAND_REASONS["tw"] == "using 3rd party programs (timewarp)"
        assert SHORTHAND_REASONS["au"] == "using 3rd party programs (auto play)"
