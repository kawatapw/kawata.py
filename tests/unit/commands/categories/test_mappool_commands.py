"""
Tests for mappool commands.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from app.commands.categories.mappool import pool_add
from app.commands.categories.mappool import pool_create
from app.commands.categories.mappool import pool_delete
from app.commands.categories.mappool import pool_help
from app.commands.categories.mappool import pool_info
from app.commands.categories.mappool import pool_list
from app.commands.categories.mappool import pool_remove
from app.commands.context import Context
from app.constants.mods import Mods
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    player.last_np = None
    return player


@pytest.fixture
def mock_context(mock_player):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.trigger = "pool"
    ctx.args = []
    ctx.recipient = Mock()
    ctx.raw_message = "!pool"

    # Mock state
    ctx.state = Mock()
    ctx.state.settings = Mock()
    ctx.state.settings.COMMAND_PREFIX = "!"

    return ctx


class TestPoolHelp:
    """Test pool help command."""

    @pytest.mark.asyncio
    async def test_help_success(self, mock_context):
        """Test getting help for mappool commands."""
        mock_context.args = []

        with patch(
            "app.commands.get_registry",
            Mock(
                return_value=Mock(
                    get_by_category=Mock(
                        return_value=[
                            Mock(
                                metadata=Mock(
                                    description="Test command",
                                    triggers=["test"],
                                ),
                                privileges=Privileges.UNRESTRICTED,
                            )
                        ]
                    )
                )
            ),
        ):
            result = await pool_help.callback(mock_context)

            assert result is not None
            assert "test:" in result
            assert "Test command" in result


class TestPoolCreate:
    """Test pool create command."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_context):
        """Test creating a mappool successfully."""
        mock_context.args = ["TestPool"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value=None),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pools_repo.create",
                AsyncMock(),
            ):
                result = await pool_create.callback(mock_context)

                assert result is not None
                assert "created" in result

    @pytest.mark.asyncio
    async def test_create_invalid_syntax(self, mock_context):
        """Test creating a mappool with invalid syntax."""
        mock_context.args = []

        result = await pool_create.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_create_pool_exists(self, mock_context):
        """Test creating a mappool that already exists."""
        mock_context.args = ["ExistingPool"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "ExistingPool"}),
        ):
            result = await pool_create.callback(mock_context)

            assert result is not None
            assert "Pool already exists" in result


class TestPoolDelete:
    """Test pool delete command."""

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_context):
        """Test deleting a mappool successfully."""
        mock_context.args = ["TestPool"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pools_repo.delete_by_id",
                AsyncMock(),
            ):
                with patch(
                    "app.commands.categories.mappool.tourney_pool_maps_repo.delete_all_in_pool",
                    AsyncMock(),
                ):
                    result = await pool_delete.callback(mock_context)

                    assert result is not None
                    assert "deleted" in result

    @pytest.mark.asyncio
    async def test_delete_invalid_syntax(self, mock_context):
        """Test deleting a mappool with invalid syntax."""
        mock_context.args = []

        result = await pool_delete.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_delete_pool_not_found(self, mock_context):
        """Test deleting a non-existent mappool."""
        mock_context.args = ["NonExistent"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value=None),
        ):
            result = await pool_delete.callback(mock_context)

            assert result is not None
            assert "Could not find a pool" in result


class TestPoolAdd:
    """Test pool add command."""

    @pytest.mark.asyncio
    async def test_add_success(self, mock_context, mock_player):
        """Test adding a map to a mappool successfully."""
        mock_context.args = ["TestPool", "HD2"]

        # Mock last_np
        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pool_maps_repo.fetch_many",
                AsyncMock(return_value=[]),
            ):
                with patch(
                    "app.commands.categories.mappool.tourney_pool_maps_repo.create",
                    AsyncMock(),
                ):
                    result = await pool_add.callback(mock_context)

                    assert result is not None
                    assert "added to" in result

    @pytest.mark.asyncio
    async def test_add_invalid_syntax(self, mock_context):
        """Test adding a map with invalid syntax."""
        mock_context.args = ["TestPool"]

        result = await pool_add.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_add_no_last_np(self, mock_context, mock_player):
        """Test adding a map without /np."""
        mock_context.args = ["TestPool", "HD2"]
        mock_player.last_np = None

        result = await pool_add.callback(mock_context)

        assert result is not None
        assert "Please /np a map first" in result

    @pytest.mark.asyncio
    async def test_add_invalid_pick_syntax(self, mock_context, mock_player):
        """Test adding a map with invalid pick syntax."""
        mock_context.args = ["TestPool", "INVALID"]

        mock_bmap = Mock()
        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        result = await pool_add.callback(mock_context)

        assert result is not None
        assert "Invalid pick syntax" in result

    @pytest.mark.asyncio
    async def test_add_pool_not_found(self, mock_context, mock_player):
        """Test adding a map to a non-existent pool."""
        mock_context.args = ["TestPool", "HD2"]

        mock_bmap = Mock()
        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value=None),
        ):
            result = await pool_add.callback(mock_context)

            assert result is not None
            assert "Could not find a pool" in result

    @pytest.mark.asyncio
    async def test_add_map_already_in_pool(self, mock_context, mock_player):
        """Test adding a map that's already in the pool."""
        mock_context.args = ["TestPool", "HD2"]

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pool_maps_repo.fetch_many",
                AsyncMock(
                    return_value=[{"map_id": 123, "mods": Mods.HIDDEN, "slot": 2}]
                ),
            ):
                with patch(
                    "app.commands.categories.mappool.Beatmap.from_bid",
                    AsyncMock(return_value=mock_bmap),
                ):
                    result = await pool_add.callback(mock_context)

                assert result is not None
                assert "already in the pool" in result


class TestPoolRemove:
    """Test pool remove command."""

    @pytest.mark.asyncio
    async def test_remove_success(self, mock_context):
        """Test removing a map from a mappool successfully."""
        mock_context.args = ["TestPool", "HD2"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pool_maps_repo.fetch_by_pool_and_pick",
                AsyncMock(return_value={"pool_id": 1, "map_id": 123}),
            ):
                with patch(
                    "app.commands.categories.mappool.tourney_pool_maps_repo.delete_map_from_pool",
                    AsyncMock(),
                ):
                    result = await pool_remove.callback(mock_context)

                    assert result is not None
                    assert "removed from" in result

    @pytest.mark.asyncio
    async def test_remove_invalid_syntax(self, mock_context):
        """Test removing a map with invalid syntax."""
        mock_context.args = ["TestPool"]

        result = await pool_remove.callback(mock_context)

        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_remove_pool_not_found(self, mock_context):
        """Test removing from a non-existent pool."""
        mock_context.args = ["TestPool", "HD2"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value=None),
        ):
            result = await pool_remove.callback(mock_context)

            assert result is not None
            assert "Could not find a pool" in result

    @pytest.mark.asyncio
    async def test_remove_pick_not_found(self, mock_context):
        """Test removing a pick that doesn't exist."""
        mock_context.args = ["TestPool", "HD2"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value={"id": 1, "name": "TestPool"}),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pool_maps_repo.fetch_by_pool_and_pick",
                AsyncMock(return_value=None),
            ):
                result = await pool_remove.callback(mock_context)

                assert result is not None
                assert "Found no" in result


class TestPoolList:
    """Test pool list command."""

    @pytest.mark.asyncio
    async def test_list_success(self, mock_context):
        """Test listing mappools."""
        mock_context.args = []

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_many",
            AsyncMock(
                return_value=[
                    {
                        "id": 1,
                        "name": "Pool1",
                        "created_by": 1,
                        "created_at": datetime(2024, 1, 15),
                    },
                    {
                        "id": 2,
                        "name": "Pool2",
                        "created_by": 1,
                        "created_at": datetime(2024, 2, 20),
                    },
                ]
            ),
        ):
            with patch(
                "app.commands.categories.mappool.users_repo.fetch_one",
                AsyncMock(return_value={"id": 1, "name": "Creator"}),
            ):
                result = await pool_list.callback(mock_context)

                assert result is not None
                assert "Mappools" in result
                assert "Pool1" in result
                assert "Pool2" in result

    @pytest.mark.asyncio
    async def test_list_no_pools(self, mock_context):
        """Test listing when no mappools exist."""
        mock_context.args = []

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_many",
            AsyncMock(return_value=[]),
        ):
            result = await pool_list.callback(mock_context)

            assert result is not None
            assert "There are currently no pools" in result


class TestPoolInfo:
    """Test pool info command."""

    @pytest.mark.asyncio
    async def test_info_success(self, mock_context):
        """Test getting mappool info."""
        mock_context.args = ["TestPool"]

        mock_bmap = Mock()
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(
                return_value={
                    "id": 1,
                    "name": "TestPool",
                    "created_by": 1,
                    "created_at": Mock(),
                }
            ),
        ):
            with patch(
                "app.commands.categories.mappool.tourney_pool_maps_repo.fetch_many",
                AsyncMock(
                    return_value=[{"map_id": 123, "mods": Mods.HIDDEN, "slot": 2}]
                ),
            ):
                with patch(
                    "app.commands.categories.mappool.Beatmap.from_bid",
                    AsyncMock(return_value=mock_bmap),
                ):
                    result = await pool_info.callback(mock_context)

                    assert result is not None
                    assert "TestPool" in result
                    assert "HD2" in result

    @pytest.mark.asyncio
    async def test_info_invalid_syntax(self, mock_context):
        """Test getting pool info with invalid syntax."""
        mock_context.args = []

        result = await pool_info.callback(mock_context)
        assert result is not None
        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_info_pool_not_found(self, mock_context):
        """Test getting info for non-existent pool."""
        mock_context.args = ["NonExistent"]

        with patch(
            "app.commands.categories.mappool.tourney_pools_repo.fetch_by_name",
            AsyncMock(return_value=None),
        ):
            result = await pool_info.callback(mock_context)

            assert result is not None
            assert "Could not find a pool" in result
