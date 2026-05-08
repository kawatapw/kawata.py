"""
Tests for developer commands.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.commands.categories.developer import (
    addpriv,
    debug,
    debug_focus,
    givedonator,
    py,
    recalc,
    reload,
    rmpriv,
    server,
    stealth,
    wipemap,
)
from app.commands.context import Context
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.DEVELOPER
    player.is_online = True
    player.stealth = False
    player.donor_end = 0
    player.last_np = None
    return player


@pytest.fixture
def mock_target_player():
    """Create a mock target player."""
    target = Mock()
    target.name = "TargetPlayer"
    target.id = 2
    target.priv = Privileges.UNRESTRICTED
    target.is_online = True
    target.donor_end = 0
    target.add_privs = AsyncMock()
    target.remove_privs = AsyncMock()
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
    ctx.state.services.database.execute = AsyncMock()
    ctx.settings = Mock()
    ctx.settings.DISCORD_INVITE = "https://discord.gg/test"
    return ctx


class TestStealthCommand:
    """Test stealth command."""

    @pytest.mark.asyncio
    async def test_stealth_enable(self, mock_context):
        """Test enabling stealth."""
        mock_context.player.stealth = False

        result = await stealth.callback(mock_context)

        assert "Stealth enabled" in result
        assert mock_context.player.stealth is True

    @pytest.mark.asyncio
    async def test_stealth_disable(self, mock_context):
        """Test disabling stealth."""
        mock_context.player.stealth = True

        result = await stealth.callback(mock_context)

        assert "Stealth disabled" in result
        assert mock_context.player.stealth is False


class TestRecalcCommand:
    """Test recalc command."""

    @pytest.mark.asyncio
    async def test_recalc(self, mock_context):
        """Test recalc command."""
        result = await recalc.callback(mock_context)

        assert "Please use tools/recalc.py instead" in result
        assert "discord.gg" in result


class TestDebugCommand:
    """Test debug command."""

    @pytest.mark.asyncio
    async def test_debug_invalid_syntax(self, mock_context):
        """Test debug command with invalid syntax."""
        mock_context.args = []

        result = await debug.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!debug <0-3>" in result

    @pytest.mark.asyncio
    async def test_debug_set_level(self, mock_context):
        """Test setting debug level."""
        mock_context.args = ["2"]

        with patch("app.commands.categories.developer.settings.DEBUG_LEVEL", Mock()):
            result = await debug.callback(mock_context)

        assert "Set Debug Level to 2" in result


class TestDebugFocusCommand:
    """Test debug_focus command."""

    @pytest.mark.asyncio
    async def test_debug_focus_invalid_syntax(self, mock_context):
        """Test debug_focus command with invalid syntax."""
        mock_context.args = []

        result = await debug_focus.callback(mock_context)

        assert "Invalid syntax" in result
        assert (
            "!debugFocus <all/scores/leaderboards/messages/requests/client>" in result
        )

    @pytest.mark.asyncio
    async def test_debug_focus_set_focus(self, mock_context):
        """Test setting debug focus."""
        mock_context.args = ["scores"]

        with patch("app.commands.categories.developer.settings.DEBUG_FOCUS", Mock()):
            result = await debug_focus.callback(mock_context)

        assert "Set Debug Focus to scores" in result


class TestAddprivCommand:
    """Test addpriv command."""

    @pytest.mark.asyncio
    async def test_addpriv_invalid_syntax(self, mock_context):
        """Test addpriv command with invalid syntax."""
        mock_context.args = ["player"]

        result = await addpriv.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!addpriv <name> <role1 role2 role3 ...>" in result

    @pytest.mark.asyncio
    async def test_addpriv_player_not_found(self, mock_context):
        """Test addpriv command when player not found."""
        mock_context.args = ["NonExistent", "mod"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await addpriv.callback(mock_context)

        assert "Could not find user." in result

    @pytest.mark.asyncio
    async def test_addpriv_invalid_role(self, mock_context, mock_target_player):
        """Test addpriv command with invalid role."""
        mock_context.args = ["TargetPlayer", "invalid_role"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await addpriv.callback(mock_context)

        assert "Not found: invalid_role" in result

    @pytest.mark.asyncio
    async def test_addpriv_donator_error(self, mock_context, mock_target_player):
        """Test addpriv command trying to add donator."""
        mock_context.args = ["TargetPlayer", "supporter"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await addpriv.callback(mock_context)

        assert "Please use the !givedonator command" in result

    @pytest.mark.asyncio
    async def test_addpriv_success(self, mock_context, mock_target_player):
        """Test addpriv command success."""
        mock_context.args = ["TargetPlayer", "mod"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await addpriv.callback(mock_context)

        assert "Updated" in result
        assert "privileges." in result
        mock_target_player.add_privs.assert_called_once()


class TestRmprivCommand:
    """Test rmpriv command."""

    @pytest.mark.asyncio
    async def test_rmpriv_invalid_syntax(self, mock_context):
        """Test rmpriv command with invalid syntax."""
        mock_context.args = ["player"]

        result = await rmpriv.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!rmpriv <name> <role1 role2 role3 ...>" in result

    @pytest.mark.asyncio
    async def test_rmpriv_player_not_found(self, mock_context):
        """Test rmpriv command when player not found."""
        mock_context.args = ["NonExistent", "mod"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await rmpriv.callback(mock_context)

        assert "Could not find user." in result

    @pytest.mark.asyncio
    async def test_rmpriv_invalid_role(self, mock_context, mock_target_player):
        """Test rmpriv command with invalid role."""
        mock_context.args = ["TargetPlayer", "invalid_role"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await rmpriv.callback(mock_context)

        assert "Not found: invalid_role" in result

    @pytest.mark.asyncio
    async def test_rmpriv_success(self, mock_context, mock_target_player):
        """Test rmpriv command success."""
        mock_context.args = ["TargetPlayer", "mod"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await rmpriv.callback(mock_context)

        assert "Updated" in result
        assert "privileges." in result
        mock_target_player.remove_privs.assert_called_once()

    @pytest.mark.asyncio
    async def test_rmpriv_donator_clears_donor_end(
        self, mock_context, mock_target_player
    ):
        """Test rmpriv command removing donator also clears donor_end."""
        mock_target_player.priv = Privileges.SUPPORTER
        mock_context.args = ["TargetPlayer", "supporter"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await rmpriv.callback(mock_context)

        assert mock_target_player.donor_end == 0
        mock_context.state.services.database.execute.assert_called_once()


class TestGivedonatorCommand:
    """Test givedonator command."""

    @pytest.mark.asyncio
    async def test_givedonator_invalid_syntax(self, mock_context):
        """Test givedonator command with invalid syntax."""
        mock_context.args = ["player"]

        result = await givedonator.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!givedonator <name> <duration>" in result

    @pytest.mark.asyncio
    async def test_givedonator_player_not_found(self, mock_context):
        """Test givedonator command when player not found."""
        mock_context.args = ["NonExistent", "30d"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=None
        )

        result = await givedonator.callback(mock_context)

        assert "Could not find user." in result

    @pytest.mark.asyncio
    async def test_givedonator_invalid_duration(self, mock_context, mock_target_player):
        """Test givedonator command with invalid duration."""
        mock_context.args = ["TargetPlayer", "invalid"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        result = await givedonator.callback(mock_context)

        assert "Invalid timespan." in result

    @pytest.mark.asyncio
    async def test_givedonator_success(self, mock_context, mock_target_player):
        """Test givedonator command success."""
        mock_context.args = ["TargetPlayer", "30d"]
        mock_context.state.sessions.players.from_cache_or_sql = AsyncMock(
            return_value=mock_target_player
        )

        with patch("app.commands.categories.developer.time.time", return_value=1000):
            result = await givedonator.callback(mock_context)

        assert "Added 30d of donator status to" in result
        assert "." in result
        mock_target_player.add_privs.assert_called_once()


class TestWipemapCommand:
    """Test wipemap command."""

    @pytest.mark.asyncio
    async def test_wipemap_invalid_syntax(self, mock_context):
        """Test wipemap command with invalid syntax."""
        mock_context.args = ["something"]

        result = await wipemap.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!wipemap" in result

    @pytest.mark.asyncio
    async def test_wipemap_no_last_np(self, mock_context):
        """Test wipemap command without last /np."""
        mock_context.args = []

        result = await wipemap.callback(mock_context)

        assert "Please /np a map first!" in result

    @pytest.mark.asyncio
    async def test_wipemap_success(self, mock_context, mock_player):
        """Test wipemap command success."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.md5 = "abc123"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        result = await wipemap.callback(mock_context)

        assert "Scores wiped." in result
        mock_context.state.services.database.execute.assert_called_once()


class TestReloadCommand:
    """Test reload command."""

    @pytest.mark.asyncio
    async def test_reload_invalid_syntax(self, mock_context):
        """Test reload command with invalid syntax."""
        mock_context.args = []

        result = await reload.callback(mock_context)

        assert "Invalid syntax" in result
        assert "!reload <module>" in result

    @pytest.mark.asyncio
    async def test_reload_module_not_found(self, mock_context):
        """Test reload command with non-existent module."""
        mock_context.args = ["nonexistent.module"]

        result = await reload.callback(mock_context)

        assert "Module not found." in result

    @pytest.mark.asyncio
    async def test_reload_success(self, mock_context):
        """Test reload command success."""
        mock_context.args = ["os"]

        with patch("app.commands.categories.developer.importlib.reload") as mock_reload:
            mock_reload.return_value = Mock(__name__="os")
            result = await reload.callback(mock_context)

        assert "Reloaded os" in result


class TestServerCommand:
    """Test server command."""

    @pytest.mark.asyncio
    async def test_server_success(self, mock_context):
        """Test server command success."""
        with patch("app.commands.categories.developer.psutil.Process") as mock_process:
            with patch(
                "app.commands.categories.developer.cpuinfo.get_cpu_info"
            ) as mock_cpu_info:
                with patch(
                    "app.commands.categories.developer.psutil.virtual_memory"
                ) as mock_memory:
                    with patch(
                        "app.commands.categories.developer.importlib.metadata.distributions"
                    ) as mock_dists:
                        mock_process.return_value.create_time.return_value = 1000
                        mock_process.return_value.memory_info.return_value = [
                            1024 * 1024 * 100
                        ]
                        mock_cpu_info.return_value = {
                            "count": 4,
                            "brand_raw": "Test CPU",
                        }
                        mock_memory.return_value.used = 1024 * 1024 * 1000
                        mock_memory.return_value.total = 1024 * 1024 * 2000
                        mock_dist = Mock()
                        mock_dist.name = "test-package"
                        mock_dist.version = "1.0.0"
                        mock_dists.return_value = [mock_dist]

                        result = await server.callback(mock_context)

        assert "bancho.py" in result
        assert "Test CPU" in result


class TestPyCommand:
    """Test py command."""

    @pytest.mark.asyncio
    async def test_py_no_args(self, mock_context):
        """Test py command with no arguments."""
        mock_context.args = []

        result = await py.callback(mock_context)

        assert "owo" in result

    @pytest.mark.asyncio
    async def test_py_with_code(self, mock_context):
        """Test py command with code."""
        mock_context.args = ["return 42"]

        result = await py.callback(mock_context)

        assert "42" in result

    @pytest.mark.asyncio
    async def test_py_with_exception(self, mock_context):
        """Test py command with exception."""
        mock_context.args = ["return 1/0"]

        result = await py.callback(mock_context)

        assert "ZeroDivisionError" in result or "Error" in result
