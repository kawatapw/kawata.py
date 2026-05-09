"""
Tests for multiplayer commands.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from app.commands.categories.multiplayer import mp_abort
from app.commands.categories.multiplayer import mp_addref
from app.commands.categories.multiplayer import mp_ban
from app.commands.categories.multiplayer import mp_condition
from app.commands.categories.multiplayer import mp_endscrim
from app.commands.categories.multiplayer import mp_force
from app.commands.categories.multiplayer import mp_freemods
from app.commands.categories.multiplayer import mp_help
from app.commands.categories.multiplayer import mp_host
from app.commands.categories.multiplayer import mp_invite
from app.commands.categories.multiplayer import mp_listref
from app.commands.categories.multiplayer import mp_loadpool
from app.commands.categories.multiplayer import mp_lock
from app.commands.categories.multiplayer import mp_map
from app.commands.categories.multiplayer import mp_mods
from app.commands.categories.multiplayer import mp_pick
from app.commands.categories.multiplayer import mp_randpw
from app.commands.categories.multiplayer import mp_rematch
from app.commands.categories.multiplayer import mp_rmref
from app.commands.categories.multiplayer import mp_scrim
from app.commands.categories.multiplayer import mp_start
from app.commands.categories.multiplayer import mp_teams
from app.commands.categories.multiplayer import mp_unban
from app.commands.categories.multiplayer import mp_unloadpool
from app.commands.categories.multiplayer import mp_unlock
from app.commands.context import Context
from app.constants.gamemodes import Mods
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import Privileges
from app.objects.match import Match
from app.objects.match import MatchTeamTypes
from app.objects.match import MatchWinConditions
from app.objects.match import SlotStatus


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    player.match = None
    return player


@pytest.fixture
def mock_match():
    """Create a mock match."""
    match = Mock(spec=Match)
    match.id = 1
    match.name = "Test Match"
    match.chat = Mock()
    match.chat.send_bot = Mock()
    match.host = None
    match.host_id = None
    match.map_id = None
    match.map_md5 = None
    match.map_name = None
    match.mode = Mock()
    match.mode.as_vanilla = 0
    match.mods = Mods.NOMOD
    match.freemods = False
    match.in_progress = False
    match.starting = None
    match.is_scrimming = False
    match.winning_pts = 0
    match.team_type = MatchTeamTypes.head_to_head
    match.win_condition = MatchWinConditions.score
    match.use_pp_scoring = False
    match.bans = set()
    match.tourney_pool = None
    match.refs = set()
    match.referees = set()
    match.slots = []
    match.winners = []
    match.match_points = {}
    match.enqueue = Mock()
    match.enqueue_state = Mock()
    match.start = Mock()
    match.unready_players = Mock()
    match.reset_players_loaded_status = Mock()
    match.reset_scrim = Mock()
    match.get_slot = Mock(return_value=Mock())
    # Create a proper mock for get_host_slot that returns a slot with Mods.NOMOD
    host_slot = Mock()
    host_slot.mods = Mods.NOMOD
    match.get_host_slot = Mock(return_value=host_slot)
    return match


@pytest.fixture
def mock_context(mock_player, mock_match):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.trigger = "mp"
    ctx.args = []
    ctx.recipient = mock_match.chat
    ctx.raw_message = "!mp"

    # Mock settings
    ctx.settings = Mock()
    ctx.settings.COMMAND_PREFIX = "!"

    # Mock state
    ctx.state = Mock()
    ctx.state.loop = Mock()
    ctx.state.loop.call_later = Mock(return_value=Mock())
    ctx.state.sessions = Mock()
    ctx.state.sessions.players = Mock()
    ctx.state.sessions.players.get = Mock(return_value=None)

    # Add player to match refs for permission checks
    mock_match.refs = {mock_player}

    return ctx


class TestMpHelp:
    """Test mp help command."""

    @pytest.mark.asyncio
    async def test_help_success(self, mock_context, mock_match):
        """Test getting help for multiplayer commands."""
        mock_context.args = []
        mock_context.player.match = mock_match

        mock_command = Mock()
        mock_command.metadata = Mock()
        mock_command.metadata.description = "Test command"
        mock_command.metadata.triggers = ["test"]
        mock_command.privileges = Privileges.UNRESTRICTED

        with patch(
            "app.commands.get_registry",
        ) as mock_registry:
            mock_registry.return_value.get_by_category = Mock(
                return_value=[mock_command],
            )
            result = await mp_help.callback(mock_context)

        assert result is not None
        assert "test:" in result
        assert "Test command" in result


class TestMpStart:
    """Test mp start command."""

    @pytest.mark.asyncio
    async def test_start_no_args_not_ready(self, mock_context, mock_match):
        """Test starting match with no args when players not ready."""
        mock_context.args = []
        mock_context.player.match = mock_match

        # Mock slots with one not ready
        slot = Mock()
        slot.status = SlotStatus.not_ready
        mock_match.slots = [slot]

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Not all players are ready" in result

    @pytest.mark.asyncio
    async def test_start_no_args_all_ready(self, mock_context, mock_match):
        """Test starting match with no args when all players ready."""
        mock_context.args = []
        mock_context.player.match = mock_match

        # Mock slots all ready
        slot = Mock()
        slot.status = SlotStatus.ready
        mock_match.slots = [slot]

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Good luck!" in result
        mock_match.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_force(self, mock_context, mock_match):
        """Test starting match with force."""
        mock_context.args = ["force"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Good luck!" in result
        mock_match.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_seconds(self, mock_context, mock_match):
        """Test starting match with timer."""
        mock_context.args = ["30"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Match will start in 30 seconds" in result

    @pytest.mark.asyncio
    async def test_start_cancel_timer(self, mock_context, mock_match):
        """Test canceling match start timer."""
        mock_context.args = ["cancel"]
        mock_context.player.match = mock_match

        mock_match.starting = {
            "start": Mock(),
            "alerts": [Mock()],
        }

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Match timer cancelled" in result

    @pytest.mark.asyncio
    async def test_start_too_many_args(self, mock_context, mock_match):
        """Test starting match with too many arguments."""
        mock_context.args = ["force", "extra"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_start_no_args_timer_active(self, mock_context, mock_match):
        """Test starting match with no args when timer already active."""
        mock_context.args = []
        mock_context.player.match = mock_match

        import time

        mock_match.starting = {"time": time.time() + 30}

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Match starting in" in result

    @pytest.mark.asyncio
    async def test_start_decimal_timer_already_active(self, mock_context, mock_match):
        """Test starting match with decimal arg when timer already active."""
        mock_context.args = ["30"]
        mock_context.player.match = mock_match

        import time

        mock_match.starting = {"time": time.time() + 60}

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Match starting in" in result

    @pytest.mark.asyncio
    async def test_start_invalid_timer_range(self, mock_context, mock_match):
        """Test starting match with out-of-range timer."""
        mock_context.args = ["0"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Timer range is 1-300 seconds" in result

    @pytest.mark.asyncio
    async def test_start_timer_too_large(self, mock_context, mock_match):
        """Test starting match with timer exceeding 300 seconds."""
        mock_context.args = ["301"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Timer range is 1-300 seconds" in result

    @pytest.mark.asyncio
    async def test_start_invalid_arg(self, mock_context, mock_match):
        """Test starting match with invalid argument."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result


class TestMpAbort:
    """Test mp abort command."""

    @pytest.mark.asyncio
    async def test_abort_success(self, mock_context, mock_match):
        """Test aborting match successfully."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.in_progress = True

        result = await mp_abort.callback(mock_context)

        assert result is not None
        assert "Match aborted" in result
        mock_match.unready_players.assert_called_once()
        mock_match.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_abort_not_in_progress(self, mock_context, mock_match):
        """Test aborting match that is not in progress."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.in_progress = False

        result = await mp_abort.callback(mock_context)

        assert result is not None
        assert "Abort what?" in result


class TestMpMap:
    """Test mp map command."""

    @pytest.mark.asyncio
    async def test_map_success(self, mock_context, mock_match):
        """Test setting match map successfully."""
        mock_context.args = ["123456"]
        mock_context.player.match = mock_match

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.md5 = "abc123"
        mock_bmap.full_name = "Test Map"
        mock_bmap.mode = Mock()

        with patch(
            "app.commands.categories.multiplayer.Beatmap.from_bid",
            AsyncMock(return_value=mock_bmap),
        ):
            result = await mp_map.callback(mock_context)

            assert result is not None
            assert "Selected:" in result
            assert mock_match.map_id == 123456
            mock_match.enqueue_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_invalid_syntax(self, mock_context, mock_match):
        """Test setting map with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_map.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_map_already_selected(self, mock_context, mock_match):
        """Test setting map that's already selected."""
        mock_context.args = ["123456"]
        mock_context.player.match = mock_match
        mock_match.map_id = 123456

        result = await mp_map.callback(mock_context)

        assert result is not None
        assert "Map already selected" in result

    @pytest.mark.asyncio
    async def test_map_not_found(self, mock_context, mock_match):
        """Test setting non-existent map."""
        mock_context.args = ["999999"]
        mock_context.player.match = mock_match

        with patch(
            "app.commands.categories.multiplayer.Beatmap.from_bid",
            AsyncMock(return_value=None),
        ):
            result = await mp_map.callback(mock_context)

            assert result is not None
            assert "Beatmap not found" in result


class TestMpMods:
    """Test mp mods command."""

    @pytest.mark.asyncio
    async def test_mods_success(self, mock_context, mock_match):
        """Test setting match mods successfully."""
        mock_context.args = ["HD"]
        mock_context.player.match = mock_match
        mock_match.freemods = False

        result = await mp_mods.callback(mock_context)

        assert result is not None
        assert "Match mods updated" in result
        mock_match.enqueue_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_mods_invalid_syntax(self, mock_context, mock_match):
        """Test setting mods with invalid syntax."""
        mock_context.args = ["H"]
        mock_context.player.match = mock_match

        result = await mp_mods.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_mods_freemods_host_sets_speed_changing(
        self, mock_context, mock_match
    ):
        """Test host setting speed-changing mods with freemods enabled."""

        mock_context.args = ["DT"]
        mock_context.player.match = mock_match
        mock_match.freemods = True
        mock_match.host = mock_context.player

        result = await mp_mods.callback(mock_context)

        assert result is not None
        assert "Match mods updated" in result
        # Host can only set speed-changing mods to match
        assert mock_match.mods == (Mods.DOUBLETIME & SPEED_CHANGING_MODS)

    @pytest.mark.asyncio
    async def test_mods_freemods_non_host_sets_slot_mods(
        self, mock_context, mock_match
    ):
        """Test non-host setting slot mods with freemods enabled."""
        mock_context.args = ["HD"]
        mock_context.player.match = mock_match
        mock_match.freemods = True
        mock_match.host = Mock()  # Different player is host

        slot = Mock()
        slot.mods = Mods.NOMOD
        mock_match.get_slot = Mock(return_value=slot)

        result = await mp_mods.callback(mock_context)

        assert result is not None
        assert "Match mods updated" in result
        # Non-host sets slot mods (non-speed-changing)
        assert slot.mods == (Mods.HIDDEN & ~SPEED_CHANGING_MODS)


class TestMpFreemods:
    """Test mp freemods command."""

    @pytest.mark.asyncio
    async def test_freemods_on(self, mock_context, mock_match):
        """Test turning freemods on."""
        mock_context.args = ["on"]
        mock_context.player.match = mock_match

        result = await mp_freemods.callback(mock_context)

        assert result is not None
        assert "Match freemod status updated" in result
        assert mock_match.freemods is True

    @pytest.mark.asyncio
    async def test_freemods_off(self, mock_context, mock_match):
        """Test turning freemods off."""
        mock_context.args = ["off"]
        mock_context.player.match = mock_match

        result = await mp_freemods.callback(mock_context)

        assert result is not None
        assert "Match freemod status updated" in result
        assert mock_match.freemods is False

    @pytest.mark.asyncio
    async def test_freemods_invalid_syntax(self, mock_context, mock_match):
        """Test freemods with invalid syntax."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_freemods.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_freemods_off_host_mods_transferred(self, mock_context, mock_match):
        """Test that turning freemods off transfers host mods to match."""
        mock_context.args = ["off"]
        mock_context.player.match = mock_match
        mock_match.freemods = True
        mock_match.mods = Mods.DOUBLETIME

        host_slot = Mock()
        host_slot.mods = Mods.HIDDEN
        mock_match.get_host_slot = Mock(return_value=host_slot)

        slot1 = Mock()
        slot1.player = Mock()
        slot1.mods = Mods.HIDDEN
        slot2 = Mock()
        slot2.player = Mock()
        slot2.mods = Mods.HARDROCK
        mock_match.slots = [slot1, slot2]

        result = await mp_freemods.callback(mock_context)

        assert result is not None
        assert "Match freemod status updated" in result
        assert mock_match.freemods is False
        # Match mods should be speed-changing | host slot mods
        assert mock_match.mods == (Mods.DOUBLETIME | Mods.HIDDEN)
        # All slot mods should be reset to NOMOD
        assert slot1.mods == Mods.NOMOD
        assert slot2.mods == Mods.NOMOD


class TestMpHost:
    """Test mp host command."""

    @pytest.mark.asyncio
    async def test_host_success(self, mock_context, mock_match):
        """Test setting match host successfully."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2
        target.enqueue = Mock()

        mock_match.slots = [Mock(player=target)]
        mock_match.host = Mock()  # Set initial host
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_host.callback(mock_context)

        assert result is not None
        assert "Match host updated" in result
        assert mock_match.host_id == 2

    @pytest.mark.asyncio
    async def test_host_invalid_syntax(self, mock_context, mock_match):
        """Test setting host with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_host.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_host_not_in_match(self, mock_context, mock_match):
        """Test setting host for player not in match."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_host.callback(mock_context)

        assert result is not None
        assert "Found no such player in the match" in result

    @pytest.mark.asyncio
    async def test_host_already_host(self, mock_context, mock_match):
        """Test setting host to the current host."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        mock_match.host = target
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_host.callback(mock_context)

        assert result is not None
        assert "already host" in result

    @pytest.mark.asyncio
    async def test_host_player_not_found(self, mock_context, mock_match):
        """Test setting host to a non-existent player."""
        mock_context.args = ["NonExistent"]
        mock_context.player.match = mock_match
        mock_context.state.sessions.players.get = Mock(return_value=None)

        result = await mp_host.callback(mock_context)

        assert result is not None
        assert "Could not find" in result


class TestMpRandpw:
    """Test mp randpw command."""

    @pytest.mark.asyncio
    async def test_randpw_success(self, mock_context, mock_match):
        """Test randomizing match password."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_randpw.callback(mock_context)

        assert result is not None
        assert "Match password randomized" in result


class TestMpInvite:
    """Test mp invite command."""

    @pytest.mark.asyncio
    async def test_invite_success(self, mock_context, mock_match):
        """Test inviting player to match."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        target.enqueue = Mock()
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_invite.callback(mock_context)

        assert result is not None
        assert "Invited" in result
        target.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_invite_invalid_syntax(self, mock_context, mock_match):
        """Test inviting with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_invite.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_invite_bot(self, mock_context, mock_match):
        """Test inviting the bot."""
        mock_context.args = ["Bot"]
        mock_context.player.match = mock_match

        bot = Mock()
        bot.name = "Bot"
        mock_context.state.sessions.bot = bot
        mock_context.state.sessions.players.get = Mock(return_value=bot)

        result = await mp_invite.callback(mock_context)

        assert result is not None
        assert "too busy" in result

    @pytest.mark.asyncio
    async def test_invite_self(self, mock_context, mock_match):
        """Test inviting yourself."""
        mock_context.args = ["TestPlayer"]
        mock_context.player.match = mock_match
        mock_context.state.sessions.players.get = Mock(return_value=mock_context.player)

        result = await mp_invite.callback(mock_context)

        assert result is not None
        assert "can't invite yourself" in result

    @pytest.mark.asyncio
    async def test_invite_player_not_found(self, mock_context, mock_match):
        """Test inviting a non-existent player."""
        mock_context.args = ["NonExistent"]
        mock_context.player.match = mock_match
        mock_context.state.sessions.players.get = Mock(return_value=None)

        result = await mp_invite.callback(mock_context)

        assert result is not None
        assert "Could not find" in result


class TestMpAddref:
    """Test mp addref command."""

    @pytest.mark.asyncio
    async def test_addref_success(self, mock_context, mock_match):
        """Test adding referee to match."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2

        mock_match.slots = [Mock(player=target)]
        mock_match.refs = {mock_context.player}  # Player must be in refs to use command
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_addref.callback(mock_context)

        assert result is not None
        assert "added to match referees" in result
        assert target in mock_match.referees

    @pytest.mark.asyncio
    async def test_addref_invalid_syntax(self, mock_context, mock_match):
        """Test adding referee with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_addref.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_addref_not_in_match(self, mock_context, mock_match):
        """Test adding referee who is not in the match."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        mock_match.slots = []  # No slots with players
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_addref.callback(mock_context)

        assert result is not None
        assert "must be in the current match" in result

    @pytest.mark.asyncio
    async def test_addref_already_ref(self, mock_context, mock_match):
        """Test adding referee who is already a ref."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        mock_match.slots = [Mock(player=target)]
        mock_match.refs = {mock_context.player, target}
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_addref.callback(mock_context)

        assert result is not None
        assert "already a match referee" in result


class TestMpRmref:
    """Test mp rmref command."""

    @pytest.mark.asyncio
    async def test_rmref_success(self, mock_context, mock_match):
        """Test removing referee from match."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2

        mock_match.refs = {mock_context.player, target}  # Player must be in refs
        mock_match.referees = {target}  # Target must be in referees to be removed
        mock_match.host = Mock()
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_rmref.callback(mock_context)

        assert result is not None
        assert "removed from match referees" in result
        assert target not in mock_match.referees

    @pytest.mark.asyncio
    async def test_rmref_invalid_syntax(self, mock_context, mock_match):
        """Test removing referee with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_rmref.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_rmref_not_a_ref(self, mock_context, mock_match):
        """Test removing a player who is not a referee."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        mock_match.refs = {mock_context.player}
        mock_match.referees = set()
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_rmref.callback(mock_context)

        assert result is not None
        assert "is not a match referee" in result

    @pytest.mark.asyncio
    async def test_rmref_is_host(self, mock_context, mock_match):
        """Test removing the host from referees."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        mock_match.refs = {mock_context.player, target}
        mock_match.referees = {target}
        mock_match.host = target
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_rmref.callback(mock_context)

        assert result is not None
        assert "host is always a referee" in result


class TestMpListref:
    """Test mp listref command."""

    @pytest.mark.asyncio
    async def test_listref_success(self, mock_context, mock_match):
        """Test listing match referees."""
        mock_context.args = []
        mock_context.player.match = mock_match

        target = Mock()
        target.name = "TargetPlayer"
        target.__str__ = Mock(return_value="TargetPlayer")
        mock_context.player.__str__ = Mock(return_value="TestPlayer")

        # Keep refs as player objects for permission check
        mock_match.refs = {mock_context.player, target}
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_listref.callback(mock_context)

        assert result is not None
        assert "TargetPlayer" in result


class TestMpLock:
    """Test mp lock command."""

    @pytest.mark.asyncio
    async def test_lock_success(self, mock_context, mock_match):
        """Test locking unused slots."""
        mock_context.args = []
        mock_context.player.match = mock_match

        slot = Mock()
        slot.status = SlotStatus.open
        mock_match.slots = [slot]

        result = await mp_lock.callback(mock_context)

        assert result is not None
        assert "All unused slots locked" in result
        assert slot.status == SlotStatus.locked


class TestMpUnlock:
    """Test mp unlock command."""

    @pytest.mark.asyncio
    async def test_unlock_success(self, mock_context, mock_match):
        """Test unlocking locked slots."""
        mock_context.args = []
        mock_context.player.match = mock_match

        slot = Mock()
        slot.status = SlotStatus.locked
        mock_match.slots = [slot]

        result = await mp_unlock.callback(mock_context)

        assert result is not None
        assert "All locked slots unlocked" in result
        assert slot.status == SlotStatus.open


class TestMpTeams:
    """Test mp teams command."""

    @pytest.mark.asyncio
    async def test_teams_head_to_head(self, mock_context, mock_match):
        """Test setting team type to head-to-head."""
        mock_context.args = ["ffa"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Match team type updated" in result
        assert mock_match.team_type == MatchTeamTypes.head_to_head

    @pytest.mark.asyncio
    async def test_teams_team_vs(self, mock_context, mock_match):
        """Test setting team type to team-vs."""
        mock_context.args = ["teams"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Match team type updated" in result
        assert mock_match.team_type == MatchTeamTypes.team_vs

    @pytest.mark.asyncio
    async def test_teams_invalid(self, mock_context, mock_match):
        """Test setting invalid team type."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Unknown team type" in result

    @pytest.mark.asyncio
    async def test_teams_tag_coop(self, mock_context, mock_match):
        """Test setting team type to tag coop."""
        mock_context.args = ["tag"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Match team type updated" in result
        assert mock_match.team_type == MatchTeamTypes.tag_coop

    @pytest.mark.asyncio
    async def test_teams_tag_team_vs(self, mock_context, mock_match):
        """Test setting team type to tag team vs."""
        mock_context.args = ["tag-teams"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Match team type updated" in result
        assert mock_match.team_type == MatchTeamTypes.tag_team_vs

    @pytest.mark.asyncio
    async def test_teams_scrim_reset(self, mock_context, mock_match):
        """Test that changing team type resets scrim scores."""
        mock_context.args = ["teams"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Match team type updated" in result
        mock_match.reset_scrim.assert_called_once()


class TestMpCondition:
    """Test mp condition command."""

    @pytest.mark.asyncio
    async def test_condition_score(self, mock_context, mock_match):
        """Test setting win condition to score."""
        mock_context.args = ["score"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Match win condition updated" in result
        assert mock_match.win_condition == MatchWinConditions.score

    @pytest.mark.asyncio
    async def test_condition_pp_during_scrim(self, mock_context, mock_match):
        """Test setting PP win condition during scrim."""
        mock_context.args = ["pp"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Match win condition updated" in result
        assert mock_match.use_pp_scoring is True

    @pytest.mark.asyncio
    async def test_condition_invalid(self, mock_context, mock_match):
        """Test setting invalid win condition."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Invalid win condition" in result

    @pytest.mark.asyncio
    async def test_condition_pp_not_scrimming(self, mock_context, mock_match):
        """Test setting PP win condition when not scrimming."""
        mock_context.args = ["pp"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = False

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "only useful as a win condition during scrims" in result

    @pytest.mark.asyncio
    async def test_condition_pp_already_enabled(self, mock_context, mock_match):
        """Test setting PP win condition when already enabled."""
        mock_context.args = ["pp"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True
        mock_match.use_pp_scoring = True

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "PP scoring already enabled" in result

    @pytest.mark.asyncio
    async def test_condition_accuracy(self, mock_context, mock_match):
        """Test setting win condition to accuracy."""
        mock_context.args = ["acc"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Match win condition updated" in result
        assert mock_match.win_condition == MatchWinConditions.accuracy

    @pytest.mark.asyncio
    async def test_condition_combo(self, mock_context, mock_match):
        """Test setting win condition to combo."""
        mock_context.args = ["combo"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Match win condition updated" in result
        assert mock_match.win_condition == MatchWinConditions.combo

    @pytest.mark.asyncio
    async def test_condition_scorev2(self, mock_context, mock_match):
        """Test setting win condition to scorev2."""
        mock_context.args = ["scorev2"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Match win condition updated" in result
        assert mock_match.win_condition == MatchWinConditions.scorev2

    @pytest.mark.asyncio
    async def test_condition_disables_pp_scoring(self, mock_context, mock_match):
        """Test that switching from PP to another condition disables PP."""
        mock_context.args = ["score"]
        mock_context.player.match = mock_match
        mock_match.use_pp_scoring = True

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Match win condition updated" in result
        assert mock_match.use_pp_scoring is False


class TestMpScrim:
    """Test mp scrim command."""

    @pytest.mark.asyncio
    async def test_scrim_start(self, mock_context, mock_match):
        """Test starting a scrim."""
        mock_context.args = ["bo3"]
        mock_context.player.match = mock_match

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        assert "scrimmage has been started" in result
        assert mock_match.is_scrimming is True

    @pytest.mark.asyncio
    async def test_scrim_end(self, mock_context, mock_match):
        """Test ending a scrim."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_endscrim.callback(mock_context)

        assert result is not None
        assert "Scrimmage ended" in result
        assert mock_match.is_scrimming is False

    @pytest.mark.asyncio
    async def test_scrim_invalid(self, mock_context, mock_match):
        """Test starting scrim with invalid syntax."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_scrim_range_too_high(self, mock_context, mock_match):
        """Test starting scrim with best of >= 16."""
        mock_context.args = ["bo17"]
        mock_context.player.match = mock_match

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        assert "Best of must be in range 0-15" in result

    @pytest.mark.asyncio
    async def test_scrim_even_number(self, mock_context, mock_match):
        """Test starting scrim with even best of."""
        mock_context.args = ["bo4"]
        mock_context.player.match = mock_match

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        assert "Best of must be an odd number" in result

    @pytest.mark.asyncio
    async def test_scrim_bo0_even_rejected(self, mock_context, mock_match):
        """Test that bo0 is rejected as even (dead code path for else)."""
        mock_context.args = ["bo0"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = False

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        # bo0 has winning_pts=1 so it enters the "real num" branch,
        # where 0 is even, so it's rejected as "odd number" required.
        assert "Best of must be an odd number" in result


class TestMpEndscrim:
    """Test mp endscrim command."""

    @pytest.mark.asyncio
    async def test_endscrim_success(self, mock_context, mock_match):
        """Test ending scrim successfully."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_endscrim.callback(mock_context)

        assert result is not None
        assert "Scrimmage ended" in result
        assert mock_match.is_scrimming is False


class TestMpRematch:
    """Test mp rematch command."""

    @pytest.mark.asyncio
    async def test_rematch_host(self, mock_context, mock_match):
        """Test rematch as host."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player  # Player is the host
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = True  # Must be scrimming for rematch
        mock_match.winners = ["TestPlayer"]  # Must have winners for point deduction
        mock_match.match_points = {"TestPlayer": 1}

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert (
            "point has been deducted" in result or "rematch has been started" in result
        )

    @pytest.mark.asyncio
    async def test_rematch_not_host(self, mock_context, mock_match):
        """Test rematch as non-host."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = Mock()  # Different player is host
        mock_match.refs = {mock_context.player}

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert "Only available to the host" in result

    @pytest.mark.asyncio
    async def test_rematch_extra_args(self, mock_context, mock_match):
        """Test rematch with extra arguments."""
        mock_context.args = ["extra"]
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_rematch_not_scrimming_no_old_points(self, mock_context, mock_match):
        """Test rematch when not scrimming and no old points."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = False
        mock_match.winning_pts = 0

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert "No scrim to rematch" in result

    @pytest.mark.asyncio
    async def test_rematch_not_scrimming_restart(self, mock_context, mock_match):
        """Test rematch restarts scrim with old points."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = False
        mock_match.winning_pts = 3

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert "rematch has been started" in result
        assert mock_match.is_scrimming is True

    @pytest.mark.asyncio
    async def test_rematch_no_winners(self, mock_context, mock_match):
        """Test rematch with no winners recorded."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = True
        mock_match.winners = []

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert "No match points have yet been awarded" in result

    @pytest.mark.asyncio
    async def test_rematch_tie_point(self, mock_context, mock_match):
        """Test rematch when last point was a tie."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = True
        mock_match.winners = [None]

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        assert "last point was a tie" in result


class TestMpForce:
    """Test mp force command."""

    @pytest.mark.asyncio
    async def test_force_success(self, mock_context, mock_match):
        """Test forcing player into match."""
        mock_context.args = ["TargetPlayer"]
        mock_context.player.match = mock_match
        mock_context.player.priv = Privileges.ADMINISTRATOR
        mock_match.passwd = "testpass"  # Required for join_match call

        target = Mock()
        target.join_match = Mock()
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await mp_force.callback(mock_context)

        assert result is not None
        assert "Welcome" in result
        target.join_match.assert_called_once()


class TestMpLoadpool:
    """Test mp loadpool command."""

    @pytest.mark.asyncio
    async def test_loadpool_success(self, mock_context, mock_match):
        """Test loading mappool into match."""
        mock_context.args = ["TestPool"]
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player  # Player is the host

        with patch(
            "app.commands.categories.multiplayer.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            result = await mp_loadpool.callback(mock_context)

            assert result is not None
            assert "selected" in result
            assert mock_match.tourney_pool is not None

    @pytest.mark.asyncio
    async def test_loadpool_already_selected(self, mock_context, mock_match):
        """Test loading a pool that is already selected."""
        mock_context.args = ["TestPool"]
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.tourney_pool = {"id": 1, "name": "TestPool"}

        with patch(
            "app.commands.categories.multiplayer.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            result = await mp_loadpool.callback(mock_context)

            assert result is not None
            assert "already selected" in result

    @pytest.mark.asyncio
    async def test_loadpool_not_host(self, mock_context, mock_match):
        """Test loading pool when not the host."""
        mock_context.args = ["TestPool"]
        mock_context.player.match = mock_match
        mock_match.host = Mock()  # Different player is host

        result = await mp_loadpool.callback(mock_context)

        assert result is not None
        assert "Only available to the host" in result


class TestMpUnloadpool:
    """Test mp unloadpool command."""

    @pytest.mark.asyncio
    async def test_unloadpool_success(self, mock_context, mock_match):
        """Test unloading mappool from match."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player  # Player is the host
        mock_match.tourney_pool = {"id": 1, "name": "TestPool"}

        result = await mp_unloadpool.callback(mock_context)

        assert result is not None
        assert "Mappool unloaded" in result
        assert mock_match.tourney_pool is None

    @pytest.mark.asyncio
    async def test_unloadpool_extra_args(self, mock_context, mock_match):
        """Test unloading pool with extra arguments."""
        mock_context.args = ["extra"]
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.tourney_pool = {"id": 1, "name": "TestPool"}

        result = await mp_unloadpool.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result


class TestMpBan:
    """Test mp ban command."""

    @pytest.mark.asyncio
    async def test_ban_success(self, mock_context, mock_match):
        """Test banning a pick."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            result = await mp_ban.callback(mock_context)

            assert result is not None
            assert "banned" in result
            assert (Mods.HIDDEN, 2) in mock_match.bans


class TestMpUnban:
    """Test mp unban command."""

    @pytest.mark.asyncio
    async def test_unban_success(self, mock_context, mock_match):
        """Test unbanning a pick."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = {(Mods.HIDDEN, 2)}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            result = await mp_unban.callback(mock_context)

            assert result is not None
            assert "unbanned" in result
            assert (Mods.HIDDEN, 2) not in mock_match.bans


class TestMpPick:
    """Test mp pick command."""

    @pytest.mark.asyncio
    async def test_pick_success(self, mock_context, mock_match):
        """Test picking a map from mappool."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        mock_bmap = Mock()
        mock_bmap.md5 = "abc123"
        mock_bmap.id = 123
        mock_bmap.full_name = "Test Map"
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            with patch(
                "app.commands.categories.multiplayer.Beatmap.from_bid",
                AsyncMock(return_value=mock_bmap),
            ):
                result = await mp_pick.callback(mock_context)

                assert result is not None
                assert "Picked" in result
                assert mock_match.map_md5 == "abc123"

    @pytest.mark.asyncio
    async def test_pick_no_pool(self, mock_context, mock_match):
        """Test picking without a pool loaded."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = None

        result = await mp_pick.callback(mock_context)

        assert result is not None
        assert "No pool currently" in result or "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_pick_invalid_syntax(self, mock_context, mock_match):
        """Test picking with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        result = await mp_pick.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_pick_map_not_found(self, mock_context, mock_match):
        """Test picking a map that doesn't exist in pool."""
        mock_context.args = ["HD99"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value=None),
        ):
            result = await mp_pick.callback(mock_context)

            assert result is not None
            assert "no" in result.lower() or "not" in result.lower()

    @pytest.mark.asyncio
    async def test_pick_banned(self, mock_context, mock_match):
        """Test picking a banned map."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = {(Mods.HIDDEN, 2)}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            result = await mp_pick.callback(mock_context)

            assert result is not None
            assert "has been banned" in result

    @pytest.mark.asyncio
    async def test_pick_beatmap_not_found(self, mock_context, mock_match):
        """Test picking a map where beatmap doesn't exist."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            with patch(
                "app.commands.categories.multiplayer.Beatmap.from_bid",
                AsyncMock(return_value=None),
            ):
                result = await mp_pick.callback(mock_context)

                assert result is not None
                assert "Found no beatmap" in result

    @pytest.mark.asyncio
    async def test_pick_freemods_disabled(self, mock_context, mock_match):
        """Test picking disables freemods and resets slot mods."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.freemods = True

        slot1 = Mock()
        slot1.player = Mock()
        slot1.mods = Mods.HIDDEN
        slot2 = Mock()
        slot2.player = Mock()
        slot2.mods = Mods.HARDROCK
        mock_match.slots = [slot1, slot2]

        mock_bmap = Mock()
        mock_bmap.md5 = "abc123"
        mock_bmap.id = 123
        mock_bmap.full_name = "Test Map"
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            with patch(
                "app.commands.categories.multiplayer.Beatmap.from_bid",
                AsyncMock(return_value=mock_bmap),
            ):
                result = await mp_pick.callback(mock_context)

                assert result is not None
                assert "Picked" in result
                assert mock_match.freemods is False
                assert slot1.mods == Mods.NOMOD
                assert slot2.mods == Mods.NOMOD


class TestMpBanEdgeCases:
    """Test mp ban command edge cases."""

    @pytest.mark.asyncio
    async def test_ban_invalid_syntax(self, mock_context, mock_match):
        """Test banning with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        result = await mp_ban.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_ban_no_pool(self, mock_context, mock_match):
        """Test banning without a pool loaded."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = None

        result = await mp_ban.callback(mock_context)

        assert result is not None
        assert "No pool currently" in result or "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_ban_invalid_pick_syntax(self, mock_context, mock_match):
        """Test banning with invalid pick syntax."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        result = await mp_ban.callback(mock_context)

        assert result is not None
        assert "Invalid pick syntax" in result

    @pytest.mark.asyncio
    async def test_ban_already_banned(self, mock_context, mock_match):
        """Test banning a pick that is already banned."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = {(Mods.HIDDEN, 2)}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            result = await mp_ban.callback(mock_context)

            assert result is not None
            assert "already banned" in result

    @pytest.mark.asyncio
    async def test_ban_map_not_in_pool(self, mock_context, mock_match):
        """Test banning a map not in the pool."""
        mock_context.args = ["HD99"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value=None),
        ):
            result = await mp_ban.callback(mock_context)

            assert result is not None
            assert "no" in result.lower() or "not" in result.lower()


class TestMpUnbanEdgeCases:
    """Test mp unban command edge cases."""

    @pytest.mark.asyncio
    async def test_unban_invalid_syntax(self, mock_context, mock_match):
        """Test unbanning with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = {(Mods.HIDDEN, 2)}

        result = await mp_unban.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_unban_invalid_pick_syntax(self, mock_context, mock_match):
        """Test unbanning with invalid pick syntax."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = {(Mods.HIDDEN, 2)}

        result = await mp_unban.callback(mock_context)

        assert result is not None
        assert "Invalid pick syntax" in result

    @pytest.mark.asyncio
    async def test_unban_no_pool(self, mock_context, mock_match):
        """Test unbanning without a pool loaded."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = None

        result = await mp_unban.callback(mock_context)

        assert result is not None
        assert "No pool currently" in result or "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_unban_not_banned(self, mock_context, mock_match):
        """Test unbanning a pick that is not currently banned."""
        mock_context.args = ["HD2"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = set()  # Nothing banned

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
        ):
            result = await mp_unban.callback(mock_context)

            assert result is not None
            assert "not currently banned" in result

    @pytest.mark.asyncio
    async def test_unban_map_not_banned(self, mock_context, mock_match):
        """Test unbanning a map that wasn't banned."""
        mock_context.args = ["HD99"]
        mock_context.player.match = mock_match
        mock_match.tourney_pool = {"id": 1}
        mock_match.bans = {(Mods.HIDDEN, 2)}  # Different pick

        with patch(
            "app.commands.categories.multiplayer.tourney_pool_maps_repo.fetch_by_pool_and_pick",
            AsyncMock(return_value={"pool_id": 1, "map_id": 999}),
        ):
            result = await mp_unban.callback(mock_context)

            assert result is not None
            # Should indicate map wasn't banned
            assert result is not None


class TestMpTeamsEdgeCases:
    """Test mp teams command edge cases."""

    @pytest.mark.asyncio
    async def test_teams_invalid_syntax(self, mock_context, mock_match):
        """Test teams with no arguments."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result


class TestMpConditionEdgeCases:
    """Test mp condition command edge cases."""

    @pytest.mark.asyncio
    async def test_condition_invalid_syntax(self, mock_context, mock_match):
        """Test condition with no arguments."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result


class TestMpScrimEdgeCases:
    """Test mp scrim command edge cases."""

    @pytest.mark.asyncio
    async def test_scrim_no_args(self, mock_context, mock_match):
        """Test scrim with no arguments (should end scrim)."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_endscrim.callback(mock_context)

        assert result is not None
        assert "Scrimmage ended" in result

    @pytest.mark.asyncio
    async def test_scrim_already_scrimming(self, mock_context, mock_match):
        """Test starting scrim when already scrimming."""
        mock_context.args = ["bo3"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        # Should indicate already scrimming or error


class TestMpRematchEdgeCases:
    """Test mp rematch command edge cases."""

    @pytest.mark.asyncio
    async def test_rematch_not_scrimming(self, mock_context, mock_match):
        """Test rematch when not scrimming."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = False  # Not scrimming

        result = await mp_rematch.callback(mock_context)

        assert result is not None
        # Should indicate not scrimming or error

    @pytest.mark.asyncio
    async def test_rematch_no_winners(self, mock_context, mock_match):
        """Test rematch with no winners recorded."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.refs = {mock_context.player}
        mock_match.is_scrimming = True
        mock_match.winners = []  # No winners

        result = await mp_rematch.callback(mock_context)

        assert result is not None


class TestMpForceEdgeCases:
    """Test mp force command edge cases."""

    @pytest.mark.asyncio
    async def test_force_invalid_syntax(self, mock_context, mock_match):
        """Test force with no arguments."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_context.player.priv = Privileges.ADMINISTRATOR

        result = await mp_force.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_force_player_not_found(self, mock_context, mock_match):
        """Test forcing a player that doesn't exist."""
        mock_context.args = ["NonExistentPlayer"]
        mock_context.player.match = mock_match
        mock_context.player.priv = Privileges.ADMINISTRATOR
        mock_context.state.sessions.players.get = Mock(return_value=None)

        result = await mp_force.callback(mock_context)

        assert result is not None
        assert "not found" in result.lower() or "Could not find" in result


class TestMpLoadpoolEdgeCases:
    """Test mp loadpool command edge cases."""

    @pytest.mark.asyncio
    async def test_loadpool_invalid_syntax(self, mock_context, mock_match):
        """Test loadpool with no arguments."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player

        result = await mp_loadpool.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_loadpool_not_found(self, mock_context, mock_match):
        """Test loading a pool that doesn't exist."""
        mock_context.args = ["NonExistentPool"]
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player

        with patch(
            "app.commands.categories.multiplayer.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value=None),
        ):
            result = await mp_loadpool.callback(mock_context)

            assert result is not None
            assert "not found" in result.lower() or "Could not find" in result

    @pytest.mark.asyncio
    async def test_loadpool_not_host(self, mock_context, mock_match):
        """Test loading pool when not the host."""
        mock_context.args = ["TestPool"]
        mock_context.player.match = mock_match
        mock_match.host = Mock()  # Different player is host

        result = await mp_loadpool.callback(mock_context)

        assert result is not None
        # Should indicate permission denied


class TestMpUnloadpoolEdgeCases:
    """Test mp unloadpool command edge cases."""

    @pytest.mark.asyncio
    async def test_unloadpool_no_pool(self, mock_context, mock_match):
        """Test unloading when no pool is loaded."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.tourney_pool = None

        result = await mp_unloadpool.callback(mock_context)

        assert result is not None
        # Should indicate no pool loaded or still work

    @pytest.mark.asyncio
    async def test_unloadpool_not_host(self, mock_context, mock_match):
        """Test unloading pool when not the host."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = Mock()  # Different player is host
        mock_match.tourney_pool = {"id": 1}

        result = await mp_unloadpool.callback(mock_context)

        assert result is not None
        # Should indicate permission denied


class TestMpHelpEdgeCases:
    """Test mp help command edge cases."""

    @pytest.mark.asyncio
    async def test_help_no_match(self, mock_context, mock_player):
        """Test mp help when player is not in a match."""
        mock_player.match = None

        result = await mp_help.callback(mock_context)

        # Should return None when not in a match
        assert result is None

    @pytest.mark.asyncio
    async def test_help_not_in_match_channel(
        self, mock_context, mock_match, mock_player
    ):
        """Test mp help when message is not in match channel."""
        mock_player.match = mock_match
        mock_context.recipient = Mock()  # Different recipient, not match chat

        result = await mp_help.callback(mock_context)

        # Should return None when not in match channel
        assert result is None

    @pytest.mark.asyncio
    async def test_help_no_permission(self, mock_context, mock_match, mock_player):
        """Test mp help when player is not a ref or tournament manager."""
        mock_player.match = mock_match
        mock_player.priv = Privileges.UNRESTRICTED  # Not tournament manager
        mock_match.refs = set()  # Player not in refs
        mock_context.recipient = mock_match.chat

        result = await mp_help.callback(mock_context)

        # Should return None when no permission
        assert result is None

    @pytest.mark.asyncio
    async def test_help_success(self, mock_context, mock_match, mock_player):
        """Test mp help shows available commands."""
        from unittest.mock import MagicMock
        from unittest.mock import patch

        from app.commands.base import Command
        from app.commands.base import CommandCategory
        from app.commands.base import CommandMetadata

        mock_player.match = mock_match
        mock_player.priv = Privileges.UNRESTRICTED
        mock_match.refs = {mock_player}
        mock_context.recipient = mock_match.chat

        # Create mock commands
        mock_cmd = MagicMock(spec=Command)
        mock_cmd.metadata = CommandMetadata(
            name="start",
            triggers=["start", "st"],
            category=CommandCategory.MULTIPLAYER,
            description="Start the match.",
        )
        mock_cmd.privileges = Privileges.UNRESTRICTED

        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = [mock_cmd]

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await mp_help.callback(mock_context)

            assert result is not None
            assert "mp start" in result.lower() or "start" in result.lower()

    @pytest.mark.asyncio
    async def test_help_excludes_hidden_commands(
        self, mock_context, mock_match, mock_player
    ):
        """Test mp help excludes commands without description."""
        from unittest.mock import MagicMock
        from unittest.mock import patch

        from app.commands.base import Command
        from app.commands.base import CommandCategory
        from app.commands.base import CommandMetadata

        mock_player.match = mock_match
        mock_player.priv = Privileges.UNRESTRICTED
        mock_match.refs = {mock_player}
        mock_context.recipient = mock_match.chat

        # Command without description (hidden)
        mock_cmd_hidden = MagicMock(spec=Command)
        mock_cmd_hidden.metadata = CommandMetadata(
            name="secret",
            triggers=["secret"],
            category=CommandCategory.MULTIPLAYER,
            description=None,
        )
        mock_cmd_hidden.privileges = Privileges.UNRESTRICTED

        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = [mock_cmd_hidden]

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await mp_help.callback(mock_context)

            assert result is not None
            # Hidden command should not appear
            assert "secret" not in result.lower()

    @pytest.mark.asyncio
    async def test_help_excludes_insufficient_privileges(
        self, mock_context, mock_match, mock_player
    ):
        """Test mp help excludes commands player can't use."""
        from unittest.mock import MagicMock
        from unittest.mock import patch

        from app.commands.base import Command
        from app.commands.base import CommandCategory
        from app.commands.base import CommandMetadata

        mock_player.match = mock_match
        mock_player.priv = Privileges.UNRESTRICTED
        mock_match.refs = {mock_player}
        mock_context.recipient = mock_match.chat

        # Command requiring admin
        mock_cmd_admin = MagicMock(spec=Command)
        mock_cmd_admin.metadata = CommandMetadata(
            name="admin_cmd",
            triggers=["admin_cmd"],
            category=CommandCategory.MULTIPLAYER,
            description="Admin command.",
        )
        mock_cmd_admin.privileges = Privileges.ADMINISTRATOR

        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = [mock_cmd_admin]

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await mp_help.callback(mock_context)

            assert result is not None
            # Admin command should not appear
            assert "admin_cmd" not in result.lower()


class TestEnsureMatchDecorator:
    """Test the ensure_match decorator edge cases."""

    @pytest.mark.asyncio
    async def test_ensure_match_player_not_in_match(self, mock_context, mock_player):
        """Test ensure_match returns None when player not in match."""
        mock_player.match = None

        # Import the decorator
        from app.commands.categories.multiplayer import ensure_match

        @ensure_match
        async def test_cmd(ctx, match):
            return "should not reach"

        result = await test_cmd(mock_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_match_message_not_in_match_channel(
        self, mock_context, mock_player, mock_match
    ):
        """Test ensure_match returns None when message not in match channel."""
        mock_player.match = mock_match
        mock_context.recipient = Mock()  # Not match chat

        from app.commands.categories.multiplayer import ensure_match

        @ensure_match
        async def test_cmd(ctx, match):
            return "should not reach"

        result = await test_cmd(mock_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_match_no_permission(
        self, mock_context, mock_player, mock_match
    ):
        """Test ensure_match returns None when player has no permission."""
        mock_player.match = mock_match
        mock_player.priv = Privileges.UNRESTRICTED
        mock_match.refs = set()
        mock_context.recipient = mock_match.chat

        from app.commands.categories.multiplayer import ensure_match

        @ensure_match
        async def test_cmd(ctx, match):
            return "should not reach"

        result = await test_cmd(mock_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_match_with_tournament_manager(
        self, mock_context, mock_player, mock_match
    ):
        """Test ensure_match allows tournament managers."""
        mock_player.match = mock_match
        mock_player.priv = Privileges.TOURNEY_MANAGER
        mock_match.refs = set()
        mock_context.recipient = mock_match.chat

        from app.commands.categories.multiplayer import ensure_match

        @ensure_match
        async def test_cmd(ctx, match):
            return "success"

        result = await test_cmd(mock_context)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_ensure_match_with_ref(self, mock_context, mock_player, mock_match):
        """Test ensure_match allows refs."""
        mock_player.match = mock_match
        mock_player.priv = Privileges.UNRESTRICTED
        mock_match.refs = {mock_player}
        mock_context.recipient = mock_match.chat

        from app.commands.categories.multiplayer import ensure_match

        @ensure_match
        async def test_cmd(ctx, match):
            return "success"

        result = await test_cmd(mock_context)
        assert result == "success"


class TestMpScrimAlreadyScrimming:
    """Test mp scrim when already scrimming."""

    @pytest.mark.asyncio
    async def test_scrim_already_scrimming(self, mock_context, mock_match):
        """Test starting scrim when already scrimming returns error."""
        mock_context.args = ["bo3"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        assert "Already scrimming" in result

    @pytest.mark.asyncio
    async def test_scrim_cancel_not_scrimming(self, mock_context, mock_match):
        """Test cancelling scrim with bo0 when not scrimming."""
        mock_context.args = ["bo0"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = False

        result = await mp_scrim.callback(mock_context)

        assert result is not None
        assert "Not currently scrimming" in result


class TestMpModsFreemodsRuntimeError:
    """Test mp_mods RuntimeError when slot not found in freemods mode."""

    @pytest.mark.asyncio
    async def test_mods_freemods_slot_not_found(self, mock_context, mock_match):
        """Test that RuntimeError is raised when player slot not found."""
        mock_context.args = ["HD"]
        mock_context.player.match = mock_match
        mock_match.freemods = True
        mock_match.host = Mock()  # Different player is host
        mock_match.get_slot = Mock(return_value=None)  # Slot not found

        with pytest.raises(RuntimeError, match="Player slot not found"):
            await mp_mods.callback(mock_context)


class TestMpFreemodsOffHostSlotNotFound:
    """Test mp_freemods RuntimeError when host slot not found in off mode."""

    @pytest.mark.asyncio
    async def test_freemods_off_host_slot_not_found(self, mock_context, mock_match):
        """Test that RuntimeError is raised when host slot not found."""
        mock_context.args = ["off"]
        mock_context.player.match = mock_match
        mock_match.freemods = True
        mock_match.get_host_slot = Mock(return_value=None)  # Host slot not found

        with pytest.raises(RuntimeError, match="Host slot not found"):
            await mp_freemods.callback(mock_context)


class TestMpUnloadpoolNoPool:
    """Test mp_unloadpool when no pool is selected."""

    @pytest.mark.asyncio
    async def test_unloadpool_no_pool_selected(self, mock_context, mock_match):
        """Test unloading when no pool is currently selected."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.host = mock_context.player
        mock_match.tourney_pool = None

        result = await mp_unloadpool.callback(mock_context)

        assert result is not None
        assert "No mappool currently selected" in result
