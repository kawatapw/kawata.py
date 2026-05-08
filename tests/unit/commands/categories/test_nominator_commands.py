"""
Tests for nominator commands.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.commands.categories.nominator import (
    _map,
    request,
    requests,
)
from app.commands.context import Context
from app.constants.privileges import Privileges
from app.objects.beatmap import RankedStatus


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.NOMINATOR
    player.last_np = None
    return player


@pytest.fixture
def mock_context(mock_player):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.trigger = "request"
    ctx.args = []
    ctx.recipient = Mock()
    ctx.raw_message = "!request"

    # Mock state
    ctx.state = Mock()
    ctx.state.settings = Mock()
    ctx.state.settings.COMMAND_PREFIX = "!"
    ctx.state.settings.REQUEST_PENDING_ONLY = False

    # Mock services and database
    ctx.state.services = Mock()
    ctx.state.services.database = Mock()

    # Mock cache
    ctx.cache = Mock()
    ctx.cache.beatmap = {}
    ctx.cache.beatmapset = {}

    return ctx


class TestRequest:
    """Test request command."""

    @pytest.mark.asyncio
    async def test_request_success(self, mock_context, mock_player):
        """Test requesting a beatmap successfully."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.status = RankedStatus.Pending

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.nominator.map_requests_repo.fetch_all",
            AsyncMock(return_value=[]),
        ):
            with patch(
                "app.commands.categories.nominator.map_requests_repo.create",
                AsyncMock(),
            ):
                result = await request.callback(mock_context)

                assert "Request submitted" in result

    @pytest.mark.asyncio
    async def test_request_invalid_syntax(self, mock_context):
        """Test request with arguments (invalid syntax)."""
        mock_context.args = ["something"]

        result = await request.callback(mock_context)

        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_request_no_last_np(self, mock_context, mock_player):
        """Test request without /np."""
        mock_context.args = []
        mock_player.last_np = None

        result = await request.callback(mock_context)

        assert "Please /np a map first" in result

    @pytest.mark.asyncio
    async def test_request_already_exists(self, mock_context, mock_player):
        """Test requesting a map already requested."""
        mock_context.args = []

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.status = RankedStatus.Pending

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.nominator.map_requests_repo.fetch_all",
            AsyncMock(return_value=[{"id": 1}]),
        ):
            result = await request.callback(mock_context)

            assert "already have an active nomination request" in result

    @pytest.mark.asyncio
    async def test_request_pending_only_setting(self, mock_context, mock_player):
        """Test request with pending only setting enabled."""
        mock_context.args = []
        mock_context.state.settings.REQUEST_PENDING_ONLY = True

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.status = RankedStatus.Ranked

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        with patch(
            "app.commands.categories.nominator.map_requests_repo.fetch_all",
            AsyncMock(return_value=[]),
        ):
            result = await request.callback(mock_context)

            assert "Only pending maps may be requested" in result


class TestRequests:
    """Test requests command."""

    @pytest.mark.asyncio
    async def test_requests_success(self, mock_context):
        """Test checking nomination request queue."""
        mock_context.args = []

        with patch(
            "app.commands.categories.nominator.map_requests_repo.fetch_all",
            AsyncMock(
                return_value=[
                    {"map_id": 123, "player_id": 1, "datetime": datetime(2024, 1, 1)},
                    {"map_id": 123, "player_id": 2, "datetime": datetime(2024, 1, 2)},
                ]
            ),
        ):
            with patch(
                "app.commands.categories.nominator.Beatmap.from_bid",
                AsyncMock(return_value=Mock(embed="[https://osu.test/b/123 Test Map]")),
            ):
                result = await requests.callback(mock_context)

                assert "Total requested beatmaps: 1" in result
                assert "2x request(s)" in result

    @pytest.mark.asyncio
    async def test_requests_empty_queue(self, mock_context):
        """Test checking empty request queue."""
        mock_context.args = []

        with patch(
            "app.commands.categories.nominator.map_requests_repo.fetch_all",
            AsyncMock(return_value=[]),
        ):
            result = await requests.callback(mock_context)

            assert "The queue is clean!" in result

    @pytest.mark.asyncio
    async def test_requests_invalid_syntax(self, mock_context):
        """Test requests with arguments (invalid syntax)."""
        mock_context.args = ["something"]

        result = await requests.callback(mock_context)

        assert "Invalid syntax" in result


class TestMap:
    """Test _map command."""

    @pytest.mark.asyncio
    async def test_map_rank_map(self, mock_context, mock_player):
        """Test ranking a single map."""
        mock_context.args = ["rank", "map"]

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_bmap.status = RankedStatus.Pending
        mock_bmap.set = Mock()
        mock_bmap.set.maps = [mock_bmap]
        mock_bmap.md5 = "test_md5"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        # Set up async context manager mock for transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_context.state.services.database.transaction = Mock(return_value=mock_transaction)

        with patch(
            "app.commands.categories.nominator.maps_repo.partial_update",
            AsyncMock(),
        ):
            with patch(
                "app.commands.categories.nominator.map_requests_repo.mark_batch_as_inactive",
                AsyncMock(),
            ):
                result = await _map.callback(mock_context)

                assert "updated to Ranked" in result

    @pytest.mark.asyncio
    async def test_map_rank_set(self, mock_context, mock_player):
        """Test ranking a whole set."""
        mock_context.args = ["rank", "set"]

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.set_id = 1
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_bmap.status = RankedStatus.Pending
        mock_bmap.set = Mock()
        mock_bmap.set.maps = [mock_bmap]
        mock_bmap.md5 = "test_md5"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        # Set up async context manager mock for transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_context.state.services.database.transaction = Mock(return_value=mock_transaction)

        # Set up cache for beatmapset (required for set ranking)
        mock_beatmapset_cache = Mock()
        mock_beatmapset_cache.maps = [mock_bmap]
        mock_context.cache.beatmapset = {1: mock_beatmapset_cache}

        with patch(
            "app.commands.categories.nominator.maps_repo.partial_update",
            AsyncMock(),
        ):
            with patch(
                "app.commands.categories.nominator.maps_repo.fetch_many",
                AsyncMock(return_value=[{"id": 123}]),
            ):
                with patch(
                    "app.commands.categories.nominator.map_requests_repo.mark_batch_as_inactive",
                    AsyncMock(),
                ):
                    result = await _map.callback(mock_context)

                    assert "updated to Ranked" in result

    @pytest.mark.asyncio
    async def test_map_unrank(self, mock_context, mock_player):
        """Test unranking a map."""
        mock_context.args = ["unrank", "map"]

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_bmap.status = RankedStatus.Ranked
        mock_bmap.set = Mock()
        mock_bmap.set.maps = [mock_bmap]
        mock_bmap.md5 = "test_md5"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        # Set up async context manager mock for transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_context.state.services.database.transaction = Mock(return_value=mock_transaction)

        with patch(
            "app.commands.categories.nominator.maps_repo.partial_update",
            AsyncMock(),
        ):
            with patch(
                "app.commands.categories.nominator.map_requests_repo.mark_batch_as_inactive",
                AsyncMock(),
            ):
                result = await _map.callback(mock_context)

                assert "updated to Unranked" in result

    @pytest.mark.asyncio
    async def test_map_love(self, mock_context, mock_player):
        """Test loving a map."""
        mock_context.args = ["love", "map"]

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_bmap.status = RankedStatus.Pending
        mock_bmap.set = Mock()
        mock_bmap.set.maps = [mock_bmap]
        mock_bmap.md5 = "test_md5"

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        # Set up async context manager mock for transaction
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_context.state.services.database.transaction = Mock(return_value=mock_transaction)

        with patch(
            "app.commands.categories.nominator.maps_repo.partial_update",
            AsyncMock(),
        ):
            with patch(
                "app.commands.categories.nominator.map_requests_repo.mark_batch_as_inactive",
                AsyncMock(),
            ):
                result = await _map.callback(mock_context)

                assert "updated to Loved" in result

    @pytest.mark.asyncio
    async def test_map_invalid_syntax(self, mock_context):
        """Test map command with invalid syntax."""
        mock_context.args = ["invalid"]

        result = await _map.callback(mock_context)

        assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_map_no_last_np(self, mock_context, mock_player):
        """Test map command without /np."""
        mock_context.args = ["rank", "map"]
        mock_player.last_np = None

        result = await _map.callback(mock_context)

        assert "Please /np a map first" in result

    @pytest.mark.asyncio
    async def test_map_already_ranked(self, mock_context, mock_player):
        """Test ranking an already ranked map."""
        mock_context.args = ["rank", "map"]

        mock_bmap = Mock()
        mock_bmap.id = 123
        mock_bmap.embed = "[https://osu.test/b/123 Test Map]"
        mock_bmap.status = RankedStatus.Ranked
        mock_bmap.set = Mock()
        mock_bmap.set.maps = [mock_bmap]

        mock_player.last_np = {
            "bmap": mock_bmap,
            "timeout": 9999999999,
        }

        result = await _map.callback(mock_context)

        assert "already Ranked" in result
