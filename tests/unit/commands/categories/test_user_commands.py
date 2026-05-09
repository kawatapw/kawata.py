"""
Tests for user commands.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from app.commands.categories.user import ParsingError
from app.commands.categories.user import _with
from app.commands.categories.user import apikey
from app.commands.categories.user import block
from app.commands.categories.user import changename
from app.commands.categories.user import maplink
from app.commands.categories.user import parse__with__command_args
from app.commands.categories.user import recent
from app.commands.categories.user import reconnect
from app.commands.categories.user import request
from app.commands.categories.user import roll
from app.commands.categories.user import top
from app.commands.categories.user import unblock
from app.commands.context import Context
from app.constants.privileges import Privileges
from app.objects.beatmap import RankedStatus


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    player.is_online = True
    player.recent_score = None
    player.blocks = []
    player.friends = []
    player.last_np = None
    player.api_key = None
    return player


@pytest.fixture
def mock_bot():
    """Create a mock bot."""
    bot = Mock()
    bot.name = "Bot"
    return bot


@pytest.fixture
def mock_context(mock_player, mock_bot):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.trigger = "test"
    ctx.args = []
    ctx.recipient = mock_player
    ctx.raw_message = "!test"

    # Mock state
    ctx.state = Mock()
    ctx.state.sessions = Mock()
    ctx.state.sessions.players = Mock()
    ctx.state.sessions.players.from_cache_or_sql = AsyncMock(return_value=None)
    ctx.state.sessions.players.get = Mock(return_value=None)
    ctx.state.sessions.bot = mock_bot
    ctx.state.services = Mock()
    ctx.state.services.database = Mock()
    ctx.state.services.database.fetch_all = AsyncMock(return_value=[])
    ctx.state.usecases = Mock()
    ctx.state.usecases.performance = Mock()
    ctx.state.usecases.performance.calculate_performances = Mock(return_value=[])

    # Also mock the global state module
    import app.state

    app.state.sessions.bot = mock_bot
    app.state.usecases = Mock()
    app.state.usecases.performance = Mock()
    app.state.usecases.performance.calculate_performances = Mock(return_value=[])

    # Mock settings
    ctx.settings = Mock()
    ctx.settings.DOMAIN = "osu.test"
    ctx.settings.MIRROR_DOWNLOAD_ENDPOINT = "https://mirror.hinamizawa.ai"
    ctx.settings.REQUEST_PENDING_ONLY = False
    ctx.settings.DISALLOWED_NAMES = ["admin", "moderator"]

    # Mock database
    ctx.database = AsyncMock()

    # Mock cache
    ctx.cache = Mock()

    # Mock command
    ctx.command = Mock()
    ctx.command.metadata = Mock()
    ctx.command.metadata.name = "test"

    return ctx


class TestRollCommand:
    """Test roll command."""

    @pytest.mark.asyncio
    async def test_roll_custom_sides(self, mock_context):
        """Test rolling with custom number of sides."""
        mock_context.args = ["6"]

        result = await roll.callback(mock_context)

        assert result is not None
        assert "TestPlayer rolls" in result
        assert "points!" in result

    @pytest.mark.asyncio
    async def test_roll_zero_sides(self, mock_context):
        """Test rolling with zero sides."""
        mock_context.args = ["0"]

        result = await roll.callback(mock_context)

        assert result == "Roll what?"

    @pytest.mark.asyncio
    async def test_roll_invalid_arg(self, mock_context):
        """Test rolling with invalid argument."""
        mock_context.args = ["abc"]

        result = await roll.callback(mock_context)

        assert result is not None
        assert "TestPlayer rolls" in result
        assert "points!" in result

    @pytest.mark.asyncio
    async def test_roll_large_number(self, mock_context):
        """Test rolling with large number."""
        mock_context.args = ["999999"]

        result = await roll.callback(mock_context)

        assert result is not None
        assert "TestPlayer rolls" in result
        assert "points!" in result


class TestBlockCommand:
    """Test block command."""

    @pytest.mark.asyncio
    async def test_block_user_success(self, mock_context, mock_player):
        """Test blocking a user successfully."""
        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2
        target.is_online = True

        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=target
        )
        mock_context.player.add_block = AsyncMock()

        result = await block.callback(mock_context)

        assert result is not None
        assert "Added TargetPlayer to blocked users." in result
        mock_context.player.add_block.assert_called_once_with(target)

    @pytest.mark.asyncio
    async def test_block_user_not_found(self, mock_context):
        """Test blocking a non-existent user."""
        mock_context.args = ["NonExistent"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await block.callback(mock_context)

        assert result is not None
        assert "User not found." in result

    @pytest.mark.asyncio
    async def test_block_bot(self, mock_context, mock_bot):
        """Test blocking the bot."""
        mock_context.args = ["Bot"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_bot
        )

        result = await block.callback(mock_context)

        assert result is not None
        assert "What?" in result

    @pytest.mark.asyncio
    async def test_block_self(self, mock_context):
        """Test blocking self."""
        mock_context.args = ["TestPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_context.player
        )

        result = await block.callback(mock_context)

        assert result is not None
        assert "What?" in result

    @pytest.mark.asyncio
    async def test_block_already_blocked(self, mock_context, mock_player):
        """Test blocking an already blocked user."""
        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2

        mock_player.blocks = [2]
        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=target
        )

        result = await block.callback(mock_context)

        assert result is not None
        assert "already blocked!" in result

    @pytest.mark.asyncio
    async def test_block_removes_from_friends(self, mock_context, mock_player):
        """Test that blocking removes from friends list."""
        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2

        mock_player.friends = [2]
        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=target
        )
        mock_context.player.add_block = AsyncMock()

        await block.callback(mock_context)

        assert 2 not in mock_player.friends


class TestUnblockCommand:
    """Test unblock command."""

    @pytest.mark.asyncio
    async def test_unblock_user_success(self, mock_context, mock_player):
        """Test unblocking a user successfully."""
        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2

        mock_player.blocks = [2]
        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=target
        )
        mock_context.player.remove_block = AsyncMock()

        result = await unblock.callback(mock_context)

        assert result is not None
        assert "Removed TargetPlayer from blocked users." in result
        mock_context.player.remove_block.assert_called_once_with(target)

    @pytest.mark.asyncio
    async def test_unblock_user_not_found(self, mock_context):
        """Test unblocking a non-existent user."""
        mock_context.args = ["NonExistent"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await unblock.callback(mock_context)

        assert result is not None
        assert "User not found." in result

    @pytest.mark.asyncio
    async def test_unblock_not_blocked(self, mock_context, mock_player):
        """Test unblocking a user that isn't blocked."""
        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2

        mock_player.blocks = []
        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=target
        )

        result = await unblock.callback(mock_context)

        assert result is not None
        assert "not blocked!" in result


class TestReconnectCommand:
    """Test reconnect command."""

    @pytest.mark.asyncio
    async def test_reconnect_self(self, mock_context, mock_player):
        """Test reconnecting self."""
        mock_context.args = []
        mock_context.player.logout = Mock()

        result = await reconnect.callback(mock_context)

        assert result is None
        mock_context.player.logout.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_other_user_as_admin(self, mock_context, mock_player):
        """Test reconnecting another user as admin."""
        target = Mock()
        target.name = "TargetPlayer"
        target.id = 2
        target.logout = Mock()

        mock_player.priv = Privileges.ADMINISTRATOR
        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await reconnect.callback(mock_context)

        assert result is None
        target.logout.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_other_user_as_regular(self, mock_context, mock_player):
        """Test reconnecting another user as regular user."""
        mock_player.priv = Privileges.UNRESTRICTED
        mock_context.args = ["TargetPlayer"]

        result = await reconnect.callback(mock_context)

        assert result is None  # Regular users can't reconnect others

    @pytest.mark.asyncio
    async def test_reconnect_player_not_found(self, mock_context, mock_player):
        """Test reconnecting non-existent player."""
        mock_player.priv = Privileges.ADMINISTRATOR
        mock_context.args = ["NonExistent"]
        mock_context.state.sessions.players.get = Mock(return_value=None)

        result = await reconnect.callback(mock_context)

        assert result is not None
        assert "Player not found" in result


class TestChangenameCommand:
    """Test changename command."""

    @pytest.mark.asyncio
    async def test_changename_valid(self, mock_context, mock_player):
        """Test changing to a valid username."""
        mock_context.args = ["NewName"]
        mock_context.player.enqueue = Mock()
        mock_context.player.logout = Mock()

        with patch(
            "app.commands.categories.user.users_repo.fetch_one",
            AsyncMock(return_value=None),
        ):
            with patch(
                "app.commands.categories.user.users_repo.partial_update",
                AsyncMock(),
            ):
                result = await changename.callback(mock_context)

                assert result is None
                mock_context.player.enqueue.assert_called_once()
                mock_context.player.logout.assert_called_once()

    @pytest.mark.asyncio
    async def test_changename_too_short(self, mock_context):
        """Test changing to a too short username."""
        mock_context.args = ["a"]  # 1 character is too short

        result = await changename.callback(mock_context)

        assert result is not None
        assert "Must be 2-15 characters in length." in result

    @pytest.mark.asyncio
    async def test_changename_too_long(self, mock_context):
        """Test changing to a too long username."""
        mock_context.args = ["ThisUsernameIsWayTooLong"]

        result = await changename.callback(mock_context)

        assert result is not None
        assert "Must be 2-15 characters in length." in result

    @pytest.mark.asyncio
    async def test_changename_invalid_chars(self, mock_context):
        """Test changing to username with invalid characters."""
        mock_context.args = ["User@Name"]

        result = await changename.callback(mock_context)

        assert result is not None
        assert "Must be 2-15 characters in length." in result

    @pytest.mark.asyncio
    async def test_changename_both_underscore_and_space(self, mock_context):
        """Test changing to username with both underscore and space."""
        mock_context.args = ["User_Name Test"]

        result = await changename.callback(mock_context)

        assert result is not None
        assert 'May contain "_" and " ", but not both.' in result

    @pytest.mark.asyncio
    async def test_changename_disallowed(self, mock_context):
        """Test changing to a disallowed username."""
        mock_context.args = ["admin"]

        with patch(
            "app.commands.categories.user.settings.DISALLOWED_NAMES",
            ["admin", "moderator"],
        ):
            result = await changename.callback(mock_context)

        assert result is not None
        assert "Disallowed username" in result

    @pytest.mark.asyncio
    async def test_changename_taken(self, mock_context):
        """Test changing to a username that's already taken."""
        mock_context.args = ["TakenName"]

        with patch(
            "app.commands.categories.user.users_repo.fetch_one",
            AsyncMock(return_value={"id": 2, "name": "TakenName"}),
        ):
            result = await changename.callback(mock_context)

        assert result is not None
        assert "Username already taken" in result


class TestMaplinkCommand:
    """Test maplink command."""

    @pytest.mark.asyncio
    async def test_maplink_from_match(self, mock_context, mock_player):
        """Test getting map link from multiplayer match."""
        match = Mock()
        match.map_id = 123456
        match.map_md5 = "abc123"

        mock_player.match = match
        mock_player.spectating = None
        mock_player.last_np = None

        mock_bmap = Mock()
        mock_bmap.set_id = 123456
        mock_bmap.full_name = "Test Map"

        with patch(
            "app.commands.categories.user.Beatmap.from_md5",
            AsyncMock(return_value=mock_bmap),
        ):
            result = await maplink.callback(mock_context)

            assert result is not None
            assert "https://mirror.hinamizawa.ai/api/v1/hinai/d/123456" in result
            assert "Test Map" in result

    @pytest.mark.asyncio
    async def test_maplink_from_spectating(self, mock_context, mock_player):
        """Test getting map link from spectating player."""
        spectating = Mock()
        spectating.status = Mock()
        spectating.status.map_id = 789012
        spectating.status.map_md5 = "def456"

        mock_player.match = None
        mock_player.spectating = spectating
        mock_player.last_np = None

        mock_bmap = Mock()
        mock_bmap.set_id = 789012
        mock_bmap.full_name = "Spectating Map"

        with patch(
            "app.commands.categories.user.Beatmap.from_md5",
            AsyncMock(return_value=mock_bmap),
        ):
            result = await maplink.callback(mock_context)

            assert result is not None
            assert "https://mirror.hinamizawa.ai/api/v1/hinai/d/789012" in result
            assert "Spectating Map" in result

    @pytest.mark.asyncio
    async def test_maplink_from_last_np(self, mock_context, mock_player):
        """Test getting map link from last /np."""
        mock_bmap = Mock()
        mock_bmap.set_id = 456789
        mock_bmap.full_name = "NP Map"

        mock_player.match = None
        mock_player.spectating = None
        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,  # Far future
        }

        result = await maplink.callback(mock_context)

        assert result is not None
        assert "https://mirror.hinamizawa.ai/api/v1/hinai/d/456789" in result
        assert "NP Map" in result

    @pytest.mark.asyncio
    async def test_maplink_no_map_found(self, mock_context, mock_player):
        """Test getting map link when no map is available."""
        mock_player.match = None
        mock_player.spectating = None
        mock_player.last_np = None

        result = await maplink.callback(mock_context)

        assert result is not None
        assert "No map found!" in result


class TestRecentCommand:
    """Test recent command."""

    @pytest.mark.asyncio
    async def test_recent_self(self, mock_context, mock_player):
        """Test getting recent score for self."""
        mock_context.args = []

        # Create a mock score
        mock_score = Mock()
        mock_score.bmap = Mock()
        mock_score.bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_score.acc = 95.5
        mock_score.mods = Mock()
        mock_score.mods.__repr__ = Mock(return_value="+HDHR")
        mock_score.mode = Mock()
        mock_score.mode.__repr__ = Mock(return_value="std")
        mock_score.passed = True
        mock_score.pp = 250.5
        mock_score.rank = 1
        mock_score.status = Mock()

        mock_player.recent_score = mock_score

        result = await recent.callback(mock_context)

        assert result is not None
        assert "Test Map" in result
        assert "95.50%" in result
        assert "+HDHR" in result
        assert "250.50pp" in result

    @pytest.mark.asyncio
    async def test_recent_other_player(self, mock_context, mock_player):
        """Test getting recent score for another player."""
        target = Mock()
        target.name = "TargetPlayer"
        target.recent_score = Mock()

        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.get = Mock(return_value=target)

        # Set up proper mock for recent_score
        mock_score = Mock()
        mock_score.bmap = Mock()
        mock_score.bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_score.acc = 95.5
        mock_score.mods = Mock()
        mock_score.mods.__repr__ = Mock(return_value="+HD")
        mock_score.mode = Mock()
        mock_score.mode.__repr__ = Mock(return_value="std")
        mock_score.passed = True
        mock_score.pp = 200.0
        mock_score.rank = 5
        mock_score.status = Mock()
        target.recent_score = mock_score

        result = await recent.callback(mock_context)

        assert result is not None
        assert "TargetPlayer" in result or "Test Map" in result

    @pytest.mark.asyncio
    async def test_recent_no_score(self, mock_context, mock_player):
        """Test getting recent score when none exists."""
        mock_context.args = []
        mock_player.recent_score = None

        result = await recent.callback(mock_context)

        assert result is not None
        assert "No scores found" in result

    @pytest.mark.asyncio
    async def test_recent_no_beatmap(self, mock_context, mock_player):
        """Test recent score with no beatmap."""
        mock_context.args = []

        mock_score = Mock()
        mock_score.bmap = None
        mock_player.recent_score = mock_score

        result = await recent.callback(mock_context)

        assert result is not None
        assert "We don't have a beatmap on file" in result

    @pytest.mark.asyncio
    async def test_recent_failed_score(self, mock_context, mock_player):
        """Test recent failed score."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.total_length = 120

        mock_score = Mock()
        mock_score.bmap = mock_bmap
        mock_score.acc = 85.0
        mock_score.mods = Mock()
        mock_score.mods.__repr__ = Mock(return_value="+HR")
        mock_score.mode = Mock()
        mock_score.mode.__repr__ = Mock(return_value="std")
        mock_score.passed = False
        mock_score.time_elapsed = 60000  # 60 seconds
        mock_player.recent_score = mock_score

        result = await recent.callback(mock_context)

        assert result is not None
        assert "FAIL" in result


class TestTopCommand:
    """Test top command."""

    @pytest.mark.asyncio
    async def test_top_valid_syntax(self, mock_context, mock_player):
        """Test top command with valid syntax."""
        mock_context.args = ["vn!std"]

        # Mock database response
        mock_scores = [
            {
                "pp": 300.5,
                "artist": "Artist",
                "title": "Title",
                "version": "Difficulty",
                "map_set_id": 123456,
                "map_id": 789012,
            }
        ]
        mock_context.state.services.database.fetch_all = AsyncMock(
            return_value=mock_scores
        )

        with patch(
            "app.commands.categories.user.users_repo.fetch_one",
            AsyncMock(return_value={"id": 1, "name": "TestPlayer"}),
        ):
            result = await top.callback(mock_context)

            assert result is not None
            assert "Top 10 scores for" in result
            assert "300.50pp" in result

    @pytest.mark.asyncio
    async def test_top_invalid_syntax(self, mock_context):
        """Test top command with invalid syntax."""
        mock_context.args = []

        result = await top.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_top_invalid_gamemode(self, mock_context):
        """Test top command with invalid gamemode."""
        mock_context.args = ["invalid_mode"]

        result = await top.callback(mock_context)

        assert result is not None
        assert "Valid gamemodes:" in result

    @pytest.mark.asyncio
    async def test_top_impossible_gamemode(self, mock_context):
        """Test top command with impossible gamemode combination."""
        mock_context.args = ["rx!mania"]

        result = await top.callback(mock_context)

        assert result is not None
        assert "Impossible gamemode combination" in result

    @pytest.mark.asyncio
    async def test_top_with_player(self, mock_context, mock_player):
        """Test top command with specified player."""
        mock_context.args = ["vn!std", "OtherPlayer"]

        mock_scores = [
            {
                "pp": 300.5,
                "artist": "Artist",
                "title": "Title",
                "version": "Difficulty",
                "map_set_id": 123456,
                "map_id": 789012,
            }
        ]
        mock_context.state.services.database.fetch_all = AsyncMock(
            return_value=mock_scores
        )

        with patch(
            "app.commands.categories.user.users_repo.fetch_one",
            AsyncMock(return_value={"id": 2, "name": "OtherPlayer"}),
        ):
            result = await top.callback(mock_context)

        assert result is not None
        assert "Top 10 scores for" in result

    @pytest.mark.asyncio
    async def test_top_no_scores(self, mock_context, mock_player):
        """Test top command when no scores exist."""
        mock_context.args = ["vn!std"]

        mock_context.state.services.database.fetch_all = AsyncMock(return_value=[])

        with patch(
            "app.commands.categories.user.users_repo.fetch_one",
            AsyncMock(return_value={"id": 1, "name": "TestPlayer"}),
        ):
            result = await top.callback(mock_context)

            assert result is not None
            assert "No scores" in result


class TestWithCommand:
    """Test _with command."""

    @pytest.mark.asyncio
    async def test_with_not_in_dm(self, mock_context, mock_bot):
        """Test _with command not in DM with bot."""
        mock_context.recipient = Mock()
        mock_context.recipient.name = "SomeChannel"

        result = await _with.callback(mock_context)

        assert result is not None
        assert "This command can only be used in DM with Bot." in result

    @pytest.mark.asyncio
    async def test_with_no_last_np(self, mock_context, mock_player, mock_bot):
        """Test _with command without last /np."""
        mock_context.recipient = mock_bot
        mock_player.last_np = None

        result = await _with.callback(mock_context)

        assert result is not None
        assert "Please /np a map first!" in result

    @pytest.mark.asyncio
    async def test_with_expired_last_np(self, mock_context, mock_player, mock_bot):
        """Test _with command with expired last /np."""
        mock_context.recipient = mock_bot
        mock_player.last_np = {
            "bmap": Mock(),
            "timeout": 0,  # Expired
        }

        result = await _with.callback(mock_context)

        assert result is not None
        assert "Please /np a map first!" in result

    @pytest.mark.asyncio
    async def test_with_valid_args(self, mock_context, mock_player, mock_bot):
        """Test _with command with valid arguments."""
        mock_context.recipient = mock_bot
        mock_context.args = ["95%", "1m", "429x", "hddt"]

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.md5 = "abc123"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "mode_vn": 0,
            "timeout": 9999999999,
        }

        # Set up calculate_performances mock on the context's usecases
        mock_context.state.usecases.performance.calculate_performances = Mock(
            return_value=[
                {
                    "performance": {"pp": 250.5},
                    "difficulty": {"stars": 5.5},
                }
            ]
        )

        with patch(
            "app.commands.categories.user.ensure_osu_file_is_available",
            AsyncMock(return_value=True),
        ):
            result = await _with.callback(mock_context)

        assert result is not None
        assert "pp" in result
        assert "*" in result


class TestRequestCommand:
    """Test request command."""

    @pytest.mark.asyncio
    async def test_request_with_args(self, mock_context):
        """Test request command with arguments."""
        mock_context.args = ["something"]

        result = await request.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_request_no_last_np(self, mock_context, mock_player):
        """Test request command without last /np."""
        mock_context.args = []
        mock_player.last_np = None

        result = await request.callback(mock_context)

        assert result is not None
        assert "Please /np a map first!" in result

    @pytest.mark.asyncio
    async def test_request_pending_only(self, mock_context, mock_player):
        """Test request command with pending only setting."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.status = RankedStatus.Ranked  # Not pending

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,  # Far future
        }

        with patch(
            "app.commands.categories.user.settings.REQUEST_PENDING_ONLY",
            True,
        ):
            result = await request.callback(mock_context)

            assert result is not None
            assert "Only pending maps may be requested" in result

    @pytest.mark.asyncio
    async def test_request_already_exists(self, mock_context, mock_player):
        """Test request command when request already exists."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.status = RankedStatus.Pending

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.user.map_requests_repo.fetch_all",
            AsyncMock(return_value=[{"id": 1}]),
        ):
            result = await request.callback(mock_context)

        assert result is not None
        assert "You already have an active nomination request" in result

    @pytest.mark.asyncio
    async def test_request_success(self, mock_context, mock_player):
        """Test successful request."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.status = RankedStatus.Pending

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.user.map_requests_repo.fetch_all",
            AsyncMock(return_value=[]),
        ):
            with patch(
                "app.commands.categories.user.map_requests_repo.create",
                AsyncMock(),
            ):
                result = await request.callback(mock_context)

        assert result is not None
        assert "Request submitted." in result


class TestApikeyCommand:
    """Test apikey command."""

    @pytest.mark.asyncio
    async def test_apikey_not_in_dm(self, mock_context, mock_bot):
        """Test apikey command not in DM with bot."""
        mock_context.recipient = Mock()
        mock_context.recipient.name = "SomeChannel"

        result = await apikey.callback(mock_context)

        assert result is not None
        assert "Command only available in DMs with" in result

    @pytest.mark.asyncio
    async def test_apikey_generate_new(self, mock_context, mock_player, mock_bot):
        """Test generating a new API key."""
        mock_context.recipient = mock_bot
        mock_player.api_key = None
        mock_context.state.sessions.api_keys = {}

        with patch(
            "app.commands.categories.user.users_repo.partial_update",
            AsyncMock(),
        ):
            result = await apikey.callback(mock_context)

            assert result is not None
            assert "API key generated" in result
            assert mock_player.api_key is not None
            assert mock_player.api_key in mock_context.state.sessions.api_keys

    @pytest.mark.asyncio
    async def test_apikey_replace_old(self, mock_context, mock_player, mock_bot):
        """Test replacing an old API key."""
        mock_context.recipient = mock_bot
        mock_player.api_key = "old-key-123"
        mock_context.state.sessions.api_keys = {"old-key-123": 1}

        with patch(
            "app.commands.categories.user.users_repo.partial_update",
            AsyncMock(),
        ):
            result = await apikey.callback(mock_context)

            assert result is not None
            assert "API key generated" in result
            assert mock_player.api_key != "old-key-123"
            assert "old-key-123" not in mock_context.state.sessions.api_keys


class TestUnblockBotOrSelf:
    """Test unblocking the bot or self."""

    @pytest.mark.asyncio
    async def test_unblock_bot(self, mock_context, mock_bot):
        """Test unblocking the bot."""
        mock_context.args = ["Bot"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_bot,
        )

        result = await unblock.callback(mock_context)

        assert result is not None
        assert "What?" in result

    @pytest.mark.asyncio
    async def test_unblock_self(self, mock_context):
        """Test unblocking self."""
        mock_context.args = ["TestPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_context.player,
        )

        result = await unblock.callback(mock_context)

        assert result is not None
        assert "What?" in result


class TestRecentOtherPlayerNotFound:
    """Test recent command when other player not found."""

    @pytest.mark.asyncio
    async def test_recent_other_not_found(self, mock_context):
        """Test recent for a non-existent player."""
        mock_context.args = ["NonExistent"]
        mock_context.state.sessions.players.get = Mock(return_value=None)

        result = await recent.callback(mock_context)

        assert result is not None
        assert "Player not found." in result


class TestTopTooManyArgs:
    """Test top command with too many arguments."""

    @pytest.mark.asyncio
    async def test_top_too_many_args(self, mock_context):
        """Test top with more than 2 arguments."""
        mock_context.args = ["vn!std", "player", "extra"]

        result = await top.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result


class TestTopPlayerNotFound:
    """Test top command when specified player not found."""

    @pytest.mark.asyncio
    async def test_top_player_not_found(self, mock_context):
        """Test top with a player that doesn't exist."""
        mock_context.args = ["vn!std", "GhostPlayer"]

        with patch(
            "app.commands.categories.user.users_repo.fetch_one",
            AsyncMock(return_value=None),
        ):
            result = await top.callback(mock_context)

            assert result is not None
            assert "Player not found." in result


class TestWithBotNone:
    """Test _with command when bot is None."""

    @pytest.mark.asyncio
    async def test_with_bot_none(self, mock_context, mock_player):
        """Test _with when bot is None."""
        mock_context.recipient = Mock()
        mock_context.recipient.name = "SomeChannel"
        mock_context.state.sessions.bot = None

        result = await _with.callback(mock_context)

        assert result is not None
        assert "This command can only be used in DM with" in result


class TestWithMapfileNotFound:
    """Test _with command when mapfile is not available."""

    @pytest.mark.asyncio
    async def test_with_mapfile_not_found(self, mock_context, mock_player, mock_bot):
        """Test _with when osu file is not available."""
        mock_context.recipient = mock_bot
        mock_context.args = ["95%"]

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.md5 = "abc123"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "mode_vn": 0,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.user.ensure_osu_file_is_available",
            AsyncMock(return_value=False),
        ):
            result = await _with.callback(mock_context)

            assert result is not None
            assert "Mapfile could not be found" in result


class TestWithParsingError:
    """Test _with command when argument parsing fails."""

    @pytest.mark.asyncio
    async def test_with_invalid_syntax(self, mock_context, mock_player, mock_bot):
        """Test _with with no arguments."""
        mock_context.recipient = mock_bot
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.id = 123456
        mock_bmap.md5 = "abc123"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "mode_vn": 0,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.user.ensure_osu_file_is_available",
            AsyncMock(return_value=True),
        ):
            result = await _with.callback(mock_context)

            assert result is not None
            assert "Invalid syntax" in result


class TestParseWithCommandArgs:
    """Test parse__with__command_args function directly."""

    def test_parse_valid_args(self):
        """Test parsing valid arguments."""
        result = parse__with__command_args(0, ["95%", "1m", "429x", "hddt"])

        assert not isinstance(result, ParsingError)
        assert result["acc"] == 95.0
        assert result["nmiss"] == 1
        assert result["combo"] == 429
        assert result["mods"] is not None

    def test_parse_empty_args(self):
        """Test parsing empty arguments."""
        result = parse__with__command_args(0, [])

        assert isinstance(result, ParsingError)
        assert "Invalid syntax" in result

    def test_parse_too_many_args(self):
        """Test parsing too many arguments."""
        result = parse__with__command_args(0, ["95%", "1m", "429x", "hddt", "extra"])

        assert isinstance(result, ParsingError)
        assert "Invalid syntax" in result

    def test_parse_unknown_arg(self):
        """Test parsing unknown argument."""
        result = parse__with__command_args(0, ["invalid"])

        assert isinstance(result, ParsingError)
        assert "Unknown argument" in result

    def test_parse_invalid_accuracy(self):
        """Test parsing accuracy out of range."""
        result = parse__with__command_args(0, ["150%"])

        assert isinstance(result, ParsingError)
        assert "Invalid accuracy" in result

    def test_parse_only_acc(self):
        """Test parsing only accuracy."""
        result = parse__with__command_args(0, ["95.5%"])

        assert not isinstance(result, ParsingError)
        assert result["acc"] == 95.5
        assert result["mods"] is None
        assert result["combo"] is None
        assert result["nmiss"] is None

    def test_parse_only_mods(self):
        """Test parsing only mods."""
        result = parse__with__command_args(0, ["+hddt"])

        assert not isinstance(result, ParsingError)
        assert result["mods"] is not None
        assert result["acc"] is None


class TestRecentOtherPlayerWithScore:
    """Test recent command for another player with a score."""

    @pytest.mark.asyncio
    async def test_recent_other_player_no_score(self, mock_context):
        """Test recent for another player who has no score."""
        target = Mock()
        target.name = "TargetPlayer"
        target.recent_score = None

        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await recent.callback(mock_context)

        assert result is not None
        assert "No scores found" in result

    @pytest.mark.asyncio
    async def test_recent_other_player_with_beatmap(self, mock_context):
        """Test recent for another player with a passed score."""
        target = Mock()
        target.name = "TargetPlayer"

        mock_score = Mock()
        mock_score.bmap = Mock()
        mock_score.bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_score.acc = 98.5
        mock_score.mods = None
        mock_score.mode = Mock()
        mock_score.mode.__repr__ = Mock(return_value="std")
        mock_score.passed = True
        mock_score.pp = 300.0
        mock_score.rank = 1
        mock_score.status = Mock()
        target.recent_score = mock_score

        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await recent.callback(mock_context)

        assert result is not None
        assert "Test Map" in result
        assert "98.50%" in result

    @pytest.mark.asyncio
    async def test_recent_other_player_failed(self, mock_context):
        """Test recent for another player with a failed score."""
        target = Mock()
        target.name = "TargetPlayer"

        mock_bmap = Mock()
        mock_bmap.total_length = 180

        mock_score = Mock()
        mock_score.bmap = mock_bmap
        mock_score.acc = 45.0
        mock_score.mods = None
        mock_score.mode = Mock()
        mock_score.mode.__repr__ = Mock(return_value="std")
        mock_score.passed = False
        mock_score.time_elapsed = 90000
        target.recent_score = mock_score

        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.get = Mock(return_value=target)

        result = await recent.callback(mock_context)

        assert result is not None
        assert "FAIL" in result
