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
from app.commands.categories.clan import clan_help
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


class TestClanHelp:
    """Test clan help command."""

    @pytest.mark.asyncio
    async def test_help_success(self, mock_context):
        """Test clan help shows available commands."""
        from unittest.mock import patch, MagicMock
        from app.commands.base import Command, CommandMetadata, CommandCategory

        # Create mock commands
        mock_cmd1 = MagicMock(spec=Command)
        mock_cmd1.metadata = CommandMetadata(
            name="create",
            triggers=["create", "c"],
            category=CommandCategory.CLAN,
            description="Create a clan.",
        )
        mock_cmd1.privileges = Privileges.UNRESTRICTED

        mock_cmd2 = MagicMock(spec=Command)
        mock_cmd2.metadata = CommandMetadata(
            name="info",
            triggers=["info", "i"],
            category=CommandCategory.CLAN,
            description="Get clan info.",
        )
        mock_cmd2.privileges = Privileges.UNRESTRICTED

        # Mock registry
        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = [mock_cmd1, mock_cmd2]

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await clan_help.callback(mock_context)

            assert result is not None
            assert "clan create" in result.lower() or "create" in result.lower()
            assert "clan info" in result.lower() or "info" in result.lower()

    @pytest.mark.asyncio
    async def test_help_no_commands(self, mock_context):
        """Test clan help when no commands available."""
        from unittest.mock import patch, MagicMock

        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = []

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await clan_help.callback(mock_context)

            # Should return empty string or message
            assert result is not None

    @pytest.mark.asyncio
    async def test_help_excludes_hidden_commands(self, mock_context):
        """Test clan help excludes commands without description."""
        from unittest.mock import patch, MagicMock
        from app.commands.base import Command, CommandMetadata, CommandCategory

        # Command without description (hidden)
        mock_cmd_hidden = MagicMock(spec=Command)
        mock_cmd_hidden.metadata = CommandMetadata(
            name="secret",
            triggers=["secret"],
            category=CommandCategory.CLAN,
            description=None,  # No description = hidden
        )
        mock_cmd_hidden.privileges = Privileges.UNRESTRICTED

        # Command with description
        mock_cmd_visible = MagicMock(spec=Command)
        mock_cmd_visible.metadata = CommandMetadata(
            name="create",
            triggers=["create"],
            category=CommandCategory.CLAN,
            description="Create a clan.",
        )
        mock_cmd_visible.privileges = Privileges.UNRESTRICTED

        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = [
            mock_cmd_hidden,
            mock_cmd_visible,
        ]

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await clan_help.callback(mock_context)

            # Should only include visible command
            assert result is not None
            # Hidden command should not appear
            assert "secret" not in result.lower()

    @pytest.mark.asyncio
    async def test_help_excludes_insufficient_privileges(self, mock_context):
        """Test clan help excludes commands player can't use."""
        from unittest.mock import patch, MagicMock
        from app.commands.base import Command, CommandMetadata, CommandCategory
        from app.constants.privileges import Privileges as Priv

        # Command requiring admin
        mock_cmd_admin = MagicMock(spec=Command)
        mock_cmd_admin.metadata = CommandMetadata(
            name="admin_cmd",
            triggers=["admin_cmd"],
            category=CommandCategory.CLAN,
            description="Admin command.",
        )
        mock_cmd_admin.privileges = Priv.ADMINISTRATOR

        # Command available to everyone
        mock_cmd_user = MagicMock(spec=Command)
        mock_cmd_user.metadata = CommandMetadata(
            name="create",
            triggers=["create"],
            category=CommandCategory.CLAN,
            description="Create a clan.",
        )
        mock_cmd_user.privileges = Privileges.UNRESTRICTED

        mock_registry = MagicMock()
        mock_registry.get_by_category.return_value = [
            mock_cmd_admin,
            mock_cmd_user,
        ]

        with patch(
            "app.commands.get_registry",
            return_value=mock_registry,
        ):
            result = await clan_help.callback(mock_context)

            assert result is not None
            # Admin command should not appear (player doesn't have admin priv)
            assert "admin_cmd" not in result.lower()


class TestClanCreateEdgeCases:
    """Test clan create command edge cases."""

    @pytest.mark.asyncio
    async def test_create_tag_too_short(self, mock_context):
        """Test creating a clan with tag too short."""
        mock_context.args = ["", "Test Clan"]

        result = await clan_create.callback(mock_context)

        assert result is not None
        assert "Clan tag may be 1-6 characters long" in result

    @pytest.mark.asyncio
    async def test_create_name_too_long(self, mock_context):
        """Test creating a clan with name too long."""
        mock_context.args = ["TAG", "A" * 20]

        result = await clan_create.callback(mock_context)

        assert result is not None
        assert "Clan name may be 2-16 characters long" in result


class TestClanDisbandEdgeCases:
    """Test clan disband command edge cases."""

    @pytest.mark.asyncio
    async def test_disband_as_owner(self, mock_context, mock_player):
        """Test owner disbanding their own clan."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Owner

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
    async def test_disband_as_member(self, mock_context, mock_player):
        """Test regular member trying to disband clan."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Member
        mock_player.priv = Privileges.UNRESTRICTED

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

                    # Member cannot disband - should show error
                    assert result is not None

    @pytest.mark.asyncio
    async def test_disband_clan_not_found_by_tag(self, mock_context, mock_player):
        """Test disbanding a clan that doesn't exist by tag."""
        mock_context.args = ["NONEXISTENT"]
        mock_player.priv = Privileges.ADMINISTRATOR
        mock_context.state.sessions.players.staff = [mock_player]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=None),
        ):
            result = await clan_disband.callback(mock_context)

            assert result is not None
            assert "Could not find a clan" in result

    @pytest.mark.asyncio
    async def test_disband_player_clan_not_found(self, mock_context, mock_player):
        """Test disbanding when player's clan no longer exists."""
        mock_context.args = []
        mock_player.clan_id = 999

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=None),
        ):
            result = await clan_disband.callback(mock_context)

            assert result is not None
            assert "not a member of a clan" in result

    @pytest.mark.asyncio
    async def test_disband_removes_all_members(self, mock_context, mock_player):
        """Test disbanding removes all members from clan."""
        mock_context.args = []
        mock_player.clan_id = 1

        clan_data = {"id": 1, "tag": "TAG", "name": "Test Clan"}
        members = [
            {"id": 1, "name": "Owner", "clan_priv": ClanPrivileges.Owner},
            {"id": 2, "name": "Member1", "clan_priv": ClanPrivileges.Member},
            {"id": 3, "name": "Member2", "clan_priv": ClanPrivileges.Member},
        ]

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=clan_data),
        ):
            with patch(
                "app.commands.categories.clan.clans_repo.delete_one",
                AsyncMock(),
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.fetch_many",
                    AsyncMock(return_value=members),
                ):
                    with patch(
                        "app.commands.categories.clan.users_repo.partial_update",
                        AsyncMock(),
                    ) as mock_update:
                        result = await clan_disband.callback(mock_context)

                        assert result is not None
                        assert "disbanded" in result
                        # Should update all members
                        assert mock_update.call_count == 3

    @pytest.mark.asyncio
    async def test_disband_updates_cached_players(self, mock_context, mock_player):
        """Test disbanding updates cached player objects."""
        mock_context.args = []
        mock_player.clan_id = 1

        clan_data = {"id": 1, "tag": "TAG", "name": "Test Clan"}
        members = [{"id": 2, "name": "Member1", "clan_priv": ClanPrivileges.Member}]

        # Mock a cached player
        cached_member = Mock()
        cached_member.clan_id = 1
        cached_member.clan_priv = ClanPrivileges.Member

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=clan_data),
        ):
            with patch(
                "app.commands.categories.clan.clans_repo.delete_one",
                AsyncMock(),
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.fetch_many",
                    AsyncMock(return_value=members),
                ):
                    with patch(
                        "app.commands.categories.clan.users_repo.partial_update",
                        AsyncMock(),
                    ):
                        # Mock the state to return a cached player
                        mock_context.state.sessions.players.get.return_value = (
                            cached_member
                        )

                        result = await clan_disband.callback(mock_context)

                        assert result is not None
                        # Cached player should be updated
                        assert cached_member.clan_id is None
                        assert cached_member.clan_priv is None


class TestClanLeaveEdgeCases:
    """Test clan leave command edge cases."""

    @pytest.mark.asyncio
    async def test_leave_as_officer(self, mock_context, mock_player):
        """Test officer trying to leave clan."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Officer

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

                    # Officer should be able to leave
                    assert result is not None

    @pytest.mark.asyncio
    async def test_leave_clan_not_found_after_check(self, mock_context, mock_player):
        """Test leaving when clan no longer exists after clan_id check."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Member

        # First fetch_one returns clan, second returns None (race condition)
        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=None),  # Clan not found
        ):
            result = await clan_leave.callback(mock_context)

            assert result is not None
            assert "not in a clan" in result

    @pytest.mark.asyncio
    async def test_leave_disbands_clan_when_last_member(self, mock_context, mock_player):
        """Test leaving a clan when you're the last member disbands it."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Member

        clan_data = {"id": 1, "tag": "TAG", "name": "Test Clan"}

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=clan_data),
        ):
            with patch(
                "app.commands.categories.clan.users_repo.fetch_many",
                AsyncMock(return_value=[]),  # No other members
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.partial_update",
                    AsyncMock(),
                ):
                    with patch(
                        "app.commands.categories.clan.clans_repo.delete_one",
                        AsyncMock(),
                    ) as mock_delete:
                        # Mock announce channel
                        mock_announce_chan = Mock()
                        mock_context.state.sessions.channels.get_by_name.return_value = (
                            mock_announce_chan
                        )

                        result = await clan_leave.callback(mock_context)

                        assert result is not None
                        assert "successfully left" in result
                        # Should delete the clan (no members left)
                        mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_leave_announces_disband_when_last_member(
        self, mock_context, mock_player
    ):
        """Test leaving announces clan disbanding when last member leaves."""
        mock_context.args = []
        mock_player.clan_id = 1
        mock_player.clan_priv = ClanPrivileges.Member

        clan_data = {"id": 1, "tag": "TAG", "name": "Test Clan"}

        with patch(
            "app.commands.categories.clan.clans_repo.fetch_one",
            AsyncMock(return_value=clan_data),
        ):
            with patch(
                "app.commands.categories.clan.users_repo.fetch_many",
                AsyncMock(return_value=[]),  # No other members
            ):
                with patch(
                    "app.commands.categories.clan.users_repo.partial_update",
                    AsyncMock(),
                ):
                    with patch(
                        "app.commands.categories.clan.clans_repo.delete_one",
                        AsyncMock(),
                    ):
                        # Mock announce channel
                        mock_announce_chan = Mock()
                        mock_announce_chan.send = Mock()
                        mock_context.state.sessions.channels.get_by_name.return_value = (
                            mock_announce_chan
                        )

                        result = await clan_leave.callback(mock_context)

                        assert result is not None
                        # Should announce disbanding
                        mock_announce_chan.send.assert_called_once()
