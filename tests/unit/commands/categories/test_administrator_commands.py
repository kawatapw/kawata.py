"""
Tests for administrator commands.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.commands.categories.administrator import (
    alert,
    alertuser,
    restrict,
    shutdown,
    switchserv,
    unrestrict,
    user,
)
from app.commands.context import Context
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.ADMINISTRATOR
    player.is_online = True
    player.last_np = None
    player.client_details = None
    player.is_bot_client = False
    player.login_time = Mock()
    player.last_recv_time = Mock()
    player.is_tourney_client = False
    player.silenced = False
    player.spectating = None
    player.recent_score = None
    player.match = None
    player.spectators = []
    player.channels = []
    player.donor_end = 0
    player.clan_id = None
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
    target.logout = Mock()
    target.last_np = None
    target.client_details = None
    target.is_bot_client = False
    target.login_time = Mock()
    target.last_recv_time = Mock()
    target.is_tourney_client = False
    target.spectating = None
    target.recent_score = None
    target.match = None
    target.spectators = []
    target.channels = []
    target.donor_end = 0
    target.clan_id = None
    target.restrict = AsyncMock()
    target.unrestrict = AsyncMock()
    return target


@pytest.fixture
def mock_context(mock_player):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.args = []
    ctx.trigger = "test"
    ctx.state = Mock()
    ctx.state.sessions = Mock()
    ctx.state.sessions.players = Mock()
    ctx.state.services = Mock()
    ctx.state.services.database = Mock()
    return ctx


class TestUserCommand:
    """Test user command."""

    @pytest.mark.asyncio
    async def test_user_self_info(self, mock_context, mock_player):
        """Test user command showing self info."""
        mock_context.args = []

        with patch(
            "app.commands.categories.administrator.timeago.format",
            return_value="2 hours ago",
        ):
            result = await user.callback(mock_context)

        assert "TestPlayer" in result
        assert "ManageUsers" in result
        assert "ManagePrivs" in result
        assert "ViewSensitiveInfo" in result

    @pytest.mark.asyncio
    async def test_user_other_player(self, mock_context, mock_target_player):
        """Test user command showing other player info."""
        mock_context.args = ["TargetPlayer"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        with patch(
            "app.commands.categories.administrator.timeago.format",
            return_value="1 hour ago",
        ):
            result = await user.callback(mock_context)

        assert "TargetPlayer" in result

    @pytest.mark.asyncio
    async def test_user_player_not_found(self, mock_context):
        """Test user command when player not found."""
        mock_context.args = ["NonExistent"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await user.callback(mock_context)

        assert "Player not found." in result


class TestRestrictCommand:
    """Test restrict command."""

    @pytest.mark.asyncio
    async def test_restrict_invalid_syntax(self, mock_context):
        """Test restrict command with invalid syntax."""
        mock_context.args = ["player"]

        result = await restrict.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!restrict <name> <reason>" in result

    @pytest.mark.asyncio
    async def test_restrict_player_not_found(self, mock_context):
        """Test restrict command when player not found."""
        mock_context.args = ["NonExistent", "cheating"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await restrict.callback(mock_context)

        assert '"NonExistent" not found.' in result

    @pytest.mark.asyncio
    async def test_restrict_staff_member_as_non_developer(
        self, mock_context, mock_target_player
    ):
        """Test restrict command on staff member as non-developer."""
        mock_target_player.priv = Privileges.MODERATOR
        mock_context.args = ["TargetPlayer", "cheating"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await restrict.callback(mock_context)

        assert "Only developers can manage staff members." in result

    @pytest.mark.asyncio
    async def test_restrict_already_restricted(self, mock_context, mock_target_player):
        """Test restrict command on already restricted player."""
        mock_target_player.restricted = True
        mock_context.args = ["TargetPlayer", "cheating"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await restrict.callback(mock_context)

        assert "already restricted!" in result

    @pytest.mark.asyncio
    async def test_restrict_success(
        self, mock_context, mock_target_player, skip_if_no_db
    ):
        """Test restrict command success."""
        mock_context.args = ["TargetPlayer", "cheating"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await restrict.callback(mock_context)

        assert "TargetPlayer was restricted." in result
        mock_target_player.restrict.assert_called_once()

    @pytest.mark.asyncio
    async def test_restrict_with_shorthand_reason(
        self, mock_context, mock_target_player, skip_if_no_db
    ):
        """Test restrict command with shorthand reason."""
        mock_context.args = ["TargetPlayer", "appeal"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await restrict.callback(mock_context)

        assert "TargetPlayer was restricted." in result
        # Verify shorthand was expanded
        mock_target_player.restrict.assert_called_once()
        call_args = mock_target_player.restrict.call_args
        assert call_args[1]["reason"] == "appeal accepted"


class TestUnrestrictCommand:
    """Test unrestrict command."""

    @pytest.mark.asyncio
    async def test_unrestrict_invalid_syntax(self, mock_context):
        """Test unrestrict command with invalid syntax."""
        mock_context.args = ["player"]

        result = await unrestrict.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!unrestrict <name> <reason>" in result

    @pytest.mark.asyncio
    async def test_unrestrict_player_not_found(self, mock_context):
        """Test unrestrict command when player not found."""
        mock_context.args = ["NonExistent", "appeal accepted"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await unrestrict.callback(mock_context)

        assert '"NonExistent" not found.' in result

    @pytest.mark.asyncio
    async def test_unrestrict_staff_member_as_non_developer(
        self, mock_context, mock_target_player
    ):
        """Test unrestrict command on staff member as non-developer."""
        mock_target_player.priv = Privileges.MODERATOR
        mock_context.args = ["TargetPlayer", "appeal accepted"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await unrestrict.callback(mock_context)

        assert "Only developers can manage staff members." in result

    @pytest.mark.asyncio
    async def test_unrestrict_not_restricted(self, mock_context, mock_target_player):
        """Test unrestrict command on player who is not restricted."""
        mock_target_player.restricted = False
        mock_context.args = ["TargetPlayer", "appeal accepted"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await unrestrict.callback(mock_context)

        assert "is not restricted!" in result

    @pytest.mark.asyncio
    async def test_unrestrict_success(
        self, mock_context, mock_target_player, skip_if_no_db
    ):
        """Test unrestrict command success."""
        mock_target_player.restricted = True
        mock_context.args = ["TargetPlayer", "appeal accepted"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await unrestrict.callback(mock_context)

        assert "TargetPlayer was unrestricted." in result
        mock_target_player.unrestrict.assert_called_once()


class TestAlertCommand:
    """Test alert command."""

    @pytest.mark.asyncio
    async def test_alert_invalid_syntax(self, mock_context):
        """Test alert command with invalid syntax."""
        mock_context.args = []

        result = await alert.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!alert <msg>" in result

    @pytest.mark.asyncio
    async def test_alert_success(self, mock_context, skip_if_no_db):
        """Test alert command success."""
        mock_context.args = ["Hello", "world"]

        result = await alert.callback(mock_context)

        assert "Alert sent." in result


class TestAlertuserCommand:
    """Test alertuser command."""

    @pytest.mark.asyncio
    async def test_alertuser_invalid_syntax(self, mock_context):
        """Test alertuser command with invalid syntax."""
        mock_context.args = ["player"]

        result = await alertuser.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!alertu <name> <msg>" in result

    @pytest.mark.asyncio
    async def test_alertuser_player_not_found(self, mock_context):
        """Test alertuser command when player not found."""
        mock_context.args = ["NonExistent", "Hello"]
        mock_context.state.sessions.players.get = Mock(return_value=None)

        result = await alertuser.callback(mock_context)

        assert "Could not find a user by that name." in result

    @pytest.mark.asyncio
    async def test_alertuser_success(self, mock_context, mock_target_player):
        """Test alertuser command success."""
        mock_context.args = ["TargetPlayer", "Hello", "world"]
        mock_context.state.sessions.players.get = Mock(return_value=mock_target_player)

        with patch.object(mock_target_player, "enqueue") as mock_enqueue:
            result = await alertuser.callback(mock_context)

        assert "Alert sent." in result
        mock_enqueue.assert_called_once()


class TestSwitchservCommand:
    """Test switchserv command."""

    @pytest.mark.asyncio
    async def test_switchserv_invalid_syntax(self, mock_context):
        """Test switchserv command with invalid syntax."""
        mock_context.args = []

        result = await switchserv.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!switch <endpoint>" in result

    @pytest.mark.asyncio
    async def test_switchserv_success(self, mock_context):
        """Test switchserv command success."""
        mock_context.args = ["127.0.0.1"]

        with patch(
            "app.commands.categories.administrator.switch_tournament_server"
        ) as mock_switch:
            mock_switch.return_value = Mock()
            result = await switchserv.callback(mock_context)

        assert "Have a nice journey.." in result
        mock_context.player.enqueue.assert_called_once()


class TestShutdownCommand:
    """Test shutdown command."""

    @pytest.mark.asyncio
    async def test_shutdown_immediate(self, mock_context):
        """Test shutdown command immediate."""
        mock_context.args = []

        with patch("app.commands.categories.administrator.os.kill") as mock_kill:
            result = await shutdown.callback(mock_context)

        assert "Process killed" in result
        mock_kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_invalid_delay(self, mock_context):
        """Test shutdown command with invalid delay."""
        mock_context.args = ["invalid"]

        result = await shutdown.callback(mock_context)

        assert "Invalid timespan." in result

    @pytest.mark.asyncio
    async def test_shutdown_delay_too_short(self, mock_context, skip_if_no_db):
        """Test shutdown command with delay too short."""
        mock_context.args = ["5s"]

        result = await shutdown.callback(mock_context)

        assert "Minimum delay is 15 seconds." in result

    @pytest.mark.asyncio
    async def test_shutdown_with_delay(self, mock_context):
        """Test shutdown command with valid delay."""
        mock_context.args = ["30s", "Maintenance"]

        import app.state

        original_loop = app.state.loop
        mock_loop = Mock()
        mock_loop.call_later = Mock()
        app.state.loop = mock_loop
        try:
            result = await shutdown.callback(mock_context)
            assert "Enqueued test." in result
            mock_loop.call_later.assert_called_once()
        finally:
            app.state.loop = original_loop
