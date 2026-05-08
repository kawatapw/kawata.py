"""
Tests for multiplayer commands.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.commands.categories.multiplayer import (
    mp_abort,
    mp_addref,
    mp_ban,
    mp_condition,
    mp_endscrim,
    mp_force,
    mp_freemods,
    mp_help,
    mp_host,
    mp_invite,
    mp_listref,
    mp_loadpool,
    mp_lock,
    mp_map,
    mp_mods,
    mp_pick,
    mp_randpw,
    mp_rematch,
    mp_rmref,
    mp_scrim,
    mp_start,
    mp_teams,
    mp_unban,
    mp_unloadpool,
    mp_unlock,
)
from app.commands.context import Context
from app.constants.gamemodes import Mods
from app.constants.privileges import Privileges
from app.objects.match import (
    Match,
    MatchTeamTypes,
    MatchWinConditions,
    SlotStatus,
)


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

        assert "Good luck!" in result
        mock_match.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_force(self, mock_context, mock_match):
        """Test starting match with force."""
        mock_context.args = ["force"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

        assert "Good luck!" in result
        mock_match.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_with_seconds(self, mock_context, mock_match):
        """Test starting match with timer."""
        mock_context.args = ["30"]
        mock_context.player.match = mock_match

        result = await mp_start.callback(mock_context)

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

        assert "Match timer cancelled" in result


class TestMpAbort:
    """Test mp abort command."""

    @pytest.mark.asyncio
    async def test_abort_success(self, mock_context, mock_match):
        """Test aborting match successfully."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.in_progress = True

        result = await mp_abort.callback(mock_context)

        assert "Match aborted" in result
        mock_match.unready_players.assert_called_once()
        mock_match.enqueue.assert_called_once()


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

            assert "Selected:" in result
            assert mock_match.map_id == 123456
            mock_match.enqueue_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_map_invalid_syntax(self, mock_context, mock_match):
        """Test setting map with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_map.callback(mock_context)

        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_map_already_selected(self, mock_context, mock_match):
        """Test setting map that's already selected."""
        mock_context.args = ["123456"]
        mock_context.player.match = mock_match
        mock_match.map_id = 123456

        result = await mp_map.callback(mock_context)

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

        assert "Match mods updated" in result
        mock_match.enqueue_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_mods_invalid_syntax(self, mock_context, mock_match):
        """Test setting mods with invalid syntax."""
        mock_context.args = ["H"]
        mock_context.player.match = mock_match

        result = await mp_mods.callback(mock_context)

        assert "Invalid syntax" in result


class TestMpFreemods:
    """Test mp freemods command."""

    @pytest.mark.asyncio
    async def test_freemods_on(self, mock_context, mock_match):
        """Test turning freemods on."""
        mock_context.args = ["on"]
        mock_context.player.match = mock_match

        result = await mp_freemods.callback(mock_context)

        assert "Match freemod status updated" in result
        assert mock_match.freemods is True

    @pytest.mark.asyncio
    async def test_freemods_off(self, mock_context, mock_match):
        """Test turning freemods off."""
        mock_context.args = ["off"]
        mock_context.player.match = mock_match

        result = await mp_freemods.callback(mock_context)

        assert "Match freemod status updated" in result
        assert mock_match.freemods is False

    @pytest.mark.asyncio
    async def test_freemods_invalid_syntax(self, mock_context, mock_match):
        """Test freemods with invalid syntax."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_freemods.callback(mock_context)

        assert "Invalid syntax" in result


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

        assert "Match host updated" in result
        assert mock_match.host_id == 2

    @pytest.mark.asyncio
    async def test_host_invalid_syntax(self, mock_context, mock_match):
        """Test setting host with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_host.callback(mock_context)

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

        assert "Found no such player in the match" in result


class TestMpRandpw:
    """Test mp randpw command."""

    @pytest.mark.asyncio
    async def test_randpw_success(self, mock_context, mock_match):
        """Test randomizing match password."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_randpw.callback(mock_context)

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

        assert "Invited" in result
        target.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_invite_invalid_syntax(self, mock_context, mock_match):
        """Test inviting with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_invite.callback(mock_context)

        assert "Invalid syntax" in result


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

        assert "added to match referees" in result
        assert target in mock_match.referees

    @pytest.mark.asyncio
    async def test_addref_invalid_syntax(self, mock_context, mock_match):
        """Test adding referee with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_addref.callback(mock_context)

        assert "Invalid syntax" in result


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

        assert "removed from match referees" in result
        assert target not in mock_match.referees

    @pytest.mark.asyncio
    async def test_rmref_invalid_syntax(self, mock_context, mock_match):
        """Test removing referee with invalid syntax."""
        mock_context.args = []
        mock_context.player.match = mock_match

        result = await mp_rmref.callback(mock_context)

        assert "Invalid syntax" in result


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

        assert "Match team type updated" in result
        assert mock_match.team_type == MatchTeamTypes.head_to_head

    @pytest.mark.asyncio
    async def test_teams_team_vs(self, mock_context, mock_match):
        """Test setting team type to team-vs."""
        mock_context.args = ["teams"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert "Match team type updated" in result
        assert mock_match.team_type == MatchTeamTypes.team_vs

    @pytest.mark.asyncio
    async def test_teams_invalid(self, mock_context, mock_match):
        """Test setting invalid team type."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_teams.callback(mock_context)

        assert "Unknown team type" in result


class TestMpCondition:
    """Test mp condition command."""

    @pytest.mark.asyncio
    async def test_condition_score(self, mock_context, mock_match):
        """Test setting win condition to score."""
        mock_context.args = ["score"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert "Match win condition updated" in result
        assert mock_match.win_condition == MatchWinConditions.score

    @pytest.mark.asyncio
    async def test_condition_pp_during_scrim(self, mock_context, mock_match):
        """Test setting PP win condition during scrim."""
        mock_context.args = ["pp"]
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_condition.callback(mock_context)

        assert "Match win condition updated" in result
        assert mock_match.use_pp_scoring is True

    @pytest.mark.asyncio
    async def test_condition_invalid(self, mock_context, mock_match):
        """Test setting invalid win condition."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_condition.callback(mock_context)

        assert "Invalid win condition" in result


class TestMpScrim:
    """Test mp scrim command."""

    @pytest.mark.asyncio
    async def test_scrim_start(self, mock_context, mock_match):
        """Test starting a scrim."""
        mock_context.args = ["bo3"]
        mock_context.player.match = mock_match

        result = await mp_scrim.callback(mock_context)

        assert "scrimmage has been started" in result
        assert mock_match.is_scrimming is True

    @pytest.mark.asyncio
    async def test_scrim_end(self, mock_context, mock_match):
        """Test ending a scrim."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_endscrim.callback(mock_context)

        assert "Scrimmage ended" in result
        assert mock_match.is_scrimming is False

    @pytest.mark.asyncio
    async def test_scrim_invalid(self, mock_context, mock_match):
        """Test starting scrim with invalid syntax."""
        mock_context.args = ["invalid"]
        mock_context.player.match = mock_match

        result = await mp_scrim.callback(mock_context)

        assert "Invalid syntax" in result


class TestMpEndscrim:
    """Test mp endscrim command."""

    @pytest.mark.asyncio
    async def test_endscrim_success(self, mock_context, mock_match):
        """Test ending scrim successfully."""
        mock_context.args = []
        mock_context.player.match = mock_match
        mock_match.is_scrimming = True

        result = await mp_endscrim.callback(mock_context)

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

        assert "Only available to the host" in result


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

            assert "selected" in result
            assert mock_match.tourney_pool is not None


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

        assert "Mappool unloaded" in result
        assert mock_match.tourney_pool is None


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

                assert "Picked" in result
                assert mock_match.map_md5 == "abc123"
