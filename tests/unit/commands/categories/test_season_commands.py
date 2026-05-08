"""
Tests for season commands.
"""

from datetime import date
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.commands.categories.season import (
    recalc_season_stats,
    season_create,
    season_end,
    season_list,
    season_schedule,
    season_start,
    seasons,
    seasons_all,
)
from app.commands.context import Context
from app.constants.privileges import Privileges


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = Mock()
    player.name = "TestPlayer"
    player.id = 1
    player.priv = Privileges.UNRESTRICTED
    player.preferred_lb_view = "all_time"
    player.selected_season_id = None
    player.send_bot = Mock()
    return player


@pytest.fixture
def mock_context(mock_player):
    """Create a mock context for testing."""
    ctx = Mock(spec=Context)
    ctx.player = mock_player
    ctx.trigger = "season"
    ctx.args = []
    ctx.recipient = Mock()
    ctx.raw_message = "!season"

    # Mock state
    ctx.state = Mock()
    ctx.state.settings = Mock()
    ctx.state.settings.COMMAND_PREFIX = "!"
    ctx.state.services = Mock()
    ctx.state.services.database = Mock()

    return ctx


class TestSeasonCreate:
    """Test season create command."""

    @pytest.mark.asyncio
    async def test_create_success(self, mock_context):
        """Test creating a season successfully."""
        mock_context.args = ["TestSeason", "1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_schedule_by_id",
                AsyncMock(
                    return_value={"id": 1, "schedule_type": "standard", "config": {}}
                ),
            ):
                with patch(
                    "app.schedule_types.get_provider_for_schedule_type",
                    Mock(
                        return_value=Mock(
                            calculate_next_season=Mock(return_value=(Mock(), Mock()))
                        )
                    ),
                ):
                    with patch(
                        "app.commands.categories.season.seasons_repo.create",
                        AsyncMock(return_value={"id": 1, "name": "TestSeason"}),
                    ):
                        result = await season_create.callback(mock_context)

                        assert "created with ID 1" in result

    @pytest.mark.asyncio
    async def test_create_disabled(self, mock_context):
        """Test creating a season when seasons are disabled."""
        mock_context.args = ["TestSeason", "1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=False),
        ):
            result = await season_create.callback(mock_context)

            assert result is None

    @pytest.mark.asyncio
    async def test_create_invalid_syntax(self, mock_context):
        """Test creating a season with invalid syntax."""
        mock_context.args = ["TestSeason"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_create.callback(mock_context)

            assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_create_schedule_not_found(self, mock_context):
        """Test creating a season with non-existent schedule."""
        mock_context.args = ["TestSeason", "999"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_schedule_by_id",
                AsyncMock(return_value=None),
            ):
                result = await season_create.callback(mock_context)

                assert "Schedule not found" in result


class TestSeasonStart:
    """Test season start command."""

    @pytest.mark.asyncio
    async def test_start_success(self, mock_context):
        """Test starting a season successfully."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(
                    return_value={"id": 1, "name": "TestSeason", "is_active": False}
                ),
            ):
                with patch(
                    "app.commands.categories.season.seasons_repo.activate",
                    AsyncMock(),
                ):
                    result = await season_start.callback(mock_context)

                    assert "activated" in result

    @pytest.mark.asyncio
    async def test_start_already_active(self, mock_context):
        """Test starting an already active season."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(
                    return_value={"id": 1, "name": "TestSeason", "is_active": True}
                ),
            ):
                result = await season_start.callback(mock_context)

                assert "already active" in result


class TestSeasonEnd:
    """Test season end command."""

    @pytest.mark.asyncio
    async def test_end_success(self, mock_context):
        """Test ending a season successfully."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(
                    return_value={"id": 1, "name": "TestSeason", "is_active": True}
                ),
            ):
                with patch(
                    "app.commands.categories.season.seasons_repo.deactivate",
                    AsyncMock(),
                ):
                    result = await season_end.callback(mock_context)

                    assert "deactivated" in result

    @pytest.mark.asyncio
    async def test_end_not_active(self, mock_context):
        """Test ending a season that's not active."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(
                    return_value={"id": 1, "name": "TestSeason", "is_active": False}
                ),
            ):
                result = await season_end.callback(mock_context)

                assert "not active" in result


class TestRecalcSeasonStats:
    """Test recalc season stats command."""

    @pytest.mark.asyncio
    async def test_recalc_all(self, mock_context):
        """Test recalculating stats for all seasons."""
        mock_context.args = ["all"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.state.services.database.fetch_all",
                AsyncMock(
                    return_value=[
                        {"id": 1, "name": "Season1"},
                        {"id": 2, "name": "Season2"},
                    ]
                ),
            ):
                with patch(
                    "app.bg_loops.calculate_season_stats_for_all_users",
                    AsyncMock(),
                ):
                    with patch(
                        "app.commands.categories.season.asyncio.create_task",
                    ):
                        result = await recalc_season_stats.callback(mock_context)

                        assert "Started recalculating 2 seasons" in result

    @pytest.mark.asyncio
    async def test_recalc_one(self, mock_context):
        """Test recalculating stats for one season."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(return_value={"id": 1, "name": "TestSeason"}),
            ):
                with patch(
                    "app.bg_loops.calculate_season_stats_for_all_users",
                    AsyncMock(),
                ):
                    with patch(
                        "app.commands.categories.season.asyncio.create_task",
                    ):
                        result = await recalc_season_stats.callback(mock_context)

                        assert "Started recalculating season 'TestSeason'" in result


class TestSeasonList:
    """Test season list command."""

    @pytest.mark.asyncio
    async def test_list_success(self, mock_context):
        """Test listing seasons."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_many",
                AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "name": "Season1",
                            "is_active": True,
                            "start_date": date(2024, 1, 1),
                            "end_date": date(2024, 3, 31),
                        },
                        {
                            "id": 2,
                            "name": "Season2",
                            "is_active": False,
                            "start_date": date(2024, 4, 1),
                            "end_date": date(2024, 6, 30),
                        },
                    ]
                ),
            ):
                result = await season_list.callback(mock_context)

                assert "Seasons (2 total)" in result
                assert "Season1" in result
                assert "Season2" in result

    @pytest.mark.asyncio
    async def test_list_no_seasons(self, mock_context):
        """Test listing when no seasons exist."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_many",
                AsyncMock(return_value=[]),
            ):
                result = await season_list.callback(mock_context)

                assert "No seasons found" in result


class TestSeasonSchedule:
    """Test season schedule command."""

    @pytest.mark.asyncio
    async def test_schedule_create(self, mock_context):
        """Test creating a schedule."""
        mock_context.args = ["create", "TestSchedule", "standard"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.schedule_types.get_provider_for_schedule_type",
                Mock(
                    return_value=Mock(
                        get_config_schema=Mock(return_value={"properties": {}})
                    )
                ),
            ):
                with patch(
                    "app.commands.categories.season.seasons_repo.create_schedule",
                    AsyncMock(return_value={"id": 1, "name": "TestSchedule"}),
                ):
                    result = await season_schedule.callback(mock_context)

                    assert "created with ID 1" in result

    @pytest.mark.asyncio
    async def test_schedule_list(self, mock_context):
        """Test listing schedules."""
        mock_context.args = ["list"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_many_schedules",
                AsyncMock(
                    return_value=[
                        {"id": 1, "name": "Schedule1", "schedule_type": "standard"},
                        {"id": 2, "name": "Schedule2", "schedule_type": "monthly"},
                    ]
                ),
            ):
                result = await season_schedule.callback(mock_context)

                assert "Schedules (2 total)" in result
                assert "Schedule1" in result

    @pytest.mark.asyncio
    async def test_schedule_invalid_action(self, mock_context):
        """Test invalid schedule action."""
        mock_context.args = ["invalid"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_schedule.callback(mock_context)

            assert "Invalid action" in result


class TestSeasons:
    """Test seasons command."""

    @pytest.mark.asyncio
    async def test_toggle_to_seasonal(self, mock_context, mock_player):
        """Test toggling to seasonal view."""
        mock_context.args = []
        mock_player.preferred_lb_view = "all_time"

        with patch(
            "app.commands.categories.season.users_repo.partial_update",
            AsyncMock(),
        ):
            result = await seasons.callback(mock_context)

            assert "Switched to seasonal view" in result
            assert mock_player.preferred_lb_view == "seasonal"

    @pytest.mark.asyncio
    async def test_toggle_to_all_time(self, mock_context, mock_player):
        """Test toggling to all-time view."""
        mock_context.args = []
        mock_player.preferred_lb_view = "seasonal"

        with patch(
            "app.commands.categories.season.users_repo.partial_update",
            AsyncMock(),
        ):
            result = await seasons.callback(mock_context)

            assert "Switched to all-time view" in result
            assert mock_player.preferred_lb_view == "all_time"

    @pytest.mark.asyncio
    async def test_view_specific_season(self, mock_context, mock_player):
        """Test viewing specific season stats."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season.seasons_repo.fetch_one",
            AsyncMock(return_value={"id": 1, "name": "TestSeason"}),
        ):
            with patch(
                "app.commands.categories.season.users_repo.partial_update",
                AsyncMock(),
            ):
                result = await seasons.callback(mock_context)

                assert "Switched to viewing season: TestSeason" in result
                assert mock_player.selected_season_id == 1

    @pytest.mark.asyncio
    async def test_view_all_time(self, mock_context, mock_player):
        """Test viewing all-time stats."""
        mock_context.args = ["all"]

        with patch(
            "app.commands.categories.season.users_repo.partial_update",
            AsyncMock(),
        ):
            result = await seasons.callback(mock_context)

            assert "Switched to all-time view" in result
            assert mock_player.preferred_lb_view == "all_time"
            assert mock_player.selected_season_id is None


class TestSeasonsAll:
    """Test seasons all command."""

    @pytest.mark.asyncio
    async def test_seasons_all(self, mock_context, mock_player):
        """Test switching to all-time view."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season.users_repo.partial_update",
            AsyncMock(),
        ):
            result = await seasons_all.callback(mock_context)

            assert "Switched to all-time view" in result
            assert mock_player.preferred_lb_view == "all_time"
