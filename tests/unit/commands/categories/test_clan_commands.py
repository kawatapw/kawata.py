"""
Tests for clan commands.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from app.commands.categories.clan import clan_create
from app.commands.categories.clan import clan_disband
from app.commands.categories.clan import clan_info
from app.commands.categories.clan import clan_leave
from app.commands.categories.clan import clan_list
from app.commands.context import Context
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    player.clan_id = None
    player.clan_priv = None
    return player


@pytest.fixture
def mock_context(mock_player):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.trigger = "clan"
    ctx.args = []
    ctx.recipient = Mock()
    ctx.raw_message = "!clan"

    # Mock state
    ctx.state = Mock()
    ctx.state.sessions = Mock()
    ctx.state.sessions.channels = Mock()
    ctx.state.sessions.players = Mock()
    ctx.state.sessions.players.staff = []

    # Mock settings
    ctx.settings = Mock()
    ctx.settings.COMMAND_PREFIX = "!"

    return ctx


class TestClanCreate:
    """Test clan create command."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_context):
        """Test creating a clan successfully."""
        mock_context.args = ["TAG", "Test Clan"]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=None),
        ):
            with patch(
                "app.commands.categories.clan.clans_repo.create",
                AsyncMock(return_value={"id": 1, "tag": "TAG", "name": "Test Clan"}),
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.partial_update",
                    AsyncMock(),
                ):
                    # Use the already mocked ctx.state.sessions.channels from fixture
                    mock_announce_chan = Mock()
                    mock_context.state.sessions.channels.get_by_name.return_value = (
                        mock_announce_chan
                    )

                    result = await clan_create.callback(mock_context)

                    assert result is not None
                    assert "founded" in result
                    assert "TAG" in result

    @pytest.mark.asyncio
    async def test_create_invalid_syntax(self, mock_context):
        """Test creating a clan with invalid syntax."""
        mock_context.args = ["TAG"]

        result = await clan_create.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_create_tag_too_long(self, mock_context):
        """Test creating a clan with tag too long."""
        mock_context.args = ["TOOLONG", "Test Clan"]

        result = await clan_create.callback(mock_context)

        assert result is not None
        assert "Clan tag may be 1-6 characters long" in result

    @pytest.mark.asyncio
    async def test_create_name_too_short(self, mock_context):
        """Test creating a clan with name too short."""
        mock_context.args = ["TAG", "A"]

        result = await clan_create.callback(mock_context)

        assert result is not None
        assert "Clan name may be 2-16 characters long" in result

    @pytest.mark.asyncio
    async def test_create_already_in_clan(self, mock_context, mock_player):
        """Test creating a clan when already in one."""
        mock_context.args = ["TAG", "Test Clan"]
        mock_player.clan_id = 1

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value={"id": 1, "tag": "OLD", "name": "Old Clan"}),
        ):
            result = await clan_create.callback(mock_context)

            assert result is not None
            assert "already a member" in result

    @pytest.mark.asyncio
    async def test_create_name_taken(self, mock_context):
        """Test creating a clan with taken name."""
        mock_context.args = ["TAG", "Test Clan"]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(side_effect=[None, {"id": 1}]),
        ):
            result = await clan_create.callback(mock_context)

            assert result is not None
            assert "already been claimed" in result

    @pytest.mark.asyncio
    async def test_create_tag_taken(self, mock_context, mock_player):
        """Test creating a clan with taken tag."""
        mock_context.args = ["TAG", "Test Clan"]
        mock_player.clan_id = 1

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(side_effect=[None, None, {"id": 1}]),
        ):
            result = await clan_create.callback(mock_context)

            assert result is not None
            assert "tag has already been claimed" in result


class TestClanDisband:
    """Test clan disband command."""

    @pytest.mark.asyncio
    async def test_disband_own_clan(self, mock_context, mock_player):
        """Test disbanding own clan."""
        mock_context.args = []
        mock_player.clan_id = 1

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value={"id": 1, "tag": "TAG", "name": "Test Clan"}),
        ):
            with patch(
                "app.commands.categories.clan.clans_repo.delete_one",
                AsyncMock(),
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.fetch_many",
                    AsyncMock(return_value=[]),
                ):
                    result = await clan_disband.callback(mock_context)

                    assert result is not None
                    assert "disbanded" in result

    @pytest.mark.asyncio
    async def test_disband_other_clan_as_admin(self, mock_context, mock_player):
        """Test admin disbanding another clan."""
        mock_context.args = ["OTHER"]
        mock_player.priv = Privileges.ADMINISTRATOR
        mock_context.state.sessions.players.staff = [mock_player]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value={"id": 2, "tag": "OTHER", "name": "Other Clan"}),
        ):
            with patch(
                "app.commands.categories.clan.clans_repo.delete_one",
                AsyncMock(),
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.fetch_many",
                    AsyncMock(return_value=[]),
                ):
                    result = await clan_disband.callback(mock_context)

                    assert result is not None
                    assert "disbanded" in result

    @pytest.mark.asyncio
    async def test_disband_other_clan_as_regular(self, mock_context):
        """Test regular user trying to disband another clan."""
        mock_context.args = ["OTHER"]

        result = await clan_disband.callback(mock_context)

        assert result is not None
        assert "Only staff members may disband" in result

    @pytest.mark.asyncio
    async def test_disband_no_clan(self, mock_context):
        """Test disbanding when not in a clan."""
        mock_context.args = []

        result = await clan_disband.callback(mock_context)

        assert result is not None
        assert "not a member of a clan" in result


class TestClanInfo:
    """Test clan info command."""

    @pytest.mark.asyncio
    async def test_info_success(self, mock_context):
        """Test getting clan info."""
        mock_context.args = ["TAG"]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(
                return_value={
                    "id": 1,
                    "tag": "TAG",
                    "name": "Test Clan",
                    "created_at": datetime(2024, 1, 15),
                }
            ),
        ):
            with patch(
                "app.commands.categories.clan.users_repo.fetch_many",
                AsyncMock(
                    return_value=[
                        {"id": 1, "name": "Owner", "clan_priv": ClanPrivileges.Owner},
                        {"id": 2, "name": "Member", "clan_priv": ClanPrivileges.Member},
                    ]
                ),
            ):
                result = await clan_info.callback(mock_context)

                assert result is not None
                assert "Test Clan" in result
                assert "Owner" in result
                assert "Member" in result

    @pytest.mark.asyncio
    async def test_info_no_args(self, mock_context):
        """Test clan info with no arguments."""
        mock_context.args = []

        result = await clan_info.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_info_clan_not_found(self, mock_context):
        """Test clan info for non-existent clan."""
        mock_context.args = ["NONEXISTENT"]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=None),
        ):
            result = await clan_info.callback(mock_context)

            assert result is not None
            assert "Could not find a clan" in result


class TestClanLeave:
    """Test clan leave command."""

    @pytest.mark.asyncio
    async def test_leave_success(self, mock_context, mock_player):
        """Test leaving a clan successfully."""
        mock_context.args = []
        mock_player.clan_id = 1

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value={"id": 1, "tag": "TAG", "name": "Test Clan"}),
        ):
            with patch(
                "app.commands.categories.clan.users_repo.fetch_many",
                AsyncMock(return_value=[{"id": 2}]),  # Other members exist
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.partial_update",
                    AsyncMock(),
                ):
                    result = await clan_leave.callback(mock_context)

                    assert result is not None
                    assert "successfully left" in result

    @pytest.mark.asyncio
    async def test_leave_no_clan(self, mock_context):
        """Test leaving when not in a clan."""
        mock_context.args = []

        result = await clan_leave.callback(mock_context)

        assert result is not None
        assert "not in a clan" in result

    @pytest.mark.asyncio
    async def test_leave_as_owner(self, mock_context, mock_player):
        """Test owner trying to leave clan."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Owner

        result = await clan_leave.callback(mock_context)

        assert result is not None
        assert "transfer your clan's ownership" in result


class TestClanList:
    """Test clan list command."""

    @pytest.mark.asyncio
    async def test_list_success(self, mock_context):
        """Test listing clans."""
        mock_context.args = []

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_many",
            AsyncMock(
                return_value=[
                    {"id": 1, "tag": "TAG1", "name": "Clan 1"},
                    {"id": 2, "tag": "TAG2", "name": "Clan 2"},
                ]
            ),
        ):
            result = await clan_list.callback(mock_context)

            assert result is not None
            assert "bancho.py clans listing" in result
            assert "TAG1" in result
            assert "TAG2" in result

    @pytest.mark.asyncio
    async def test_list_with_page(self, mock_context):
        """Test listing clans with page number."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_many",
            AsyncMock(
                return_value=[
                    {"id": i, "tag": f"T{i}", "name": f"Clan {i}"} for i in range(30)
                ]
            ),
        ):
            result = await clan_list.callback(mock_context)

            assert result is not None
            assert "bancho.py clans listing" in result

    @pytest.mark.asyncio
    async def test_list_no_clans(self, mock_context):
        """Test listing when no clans exist."""
        mock_context.args = []

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_many",
            AsyncMock(return_value=[]),
        ):
            result = await clan_list.callback(mock_context)

            assert result is not None
            assert "No clans found" in result

    @pytest.mark.asyncio
    async def test_list_invalid_page(self, mock_context):
        """Test listing with invalid page number."""
        mock_context.args = ["abc"]

        result = await clan_list.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result
