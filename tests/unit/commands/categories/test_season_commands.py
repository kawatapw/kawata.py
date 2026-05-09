"""
Tests for season commands.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from app.commands.categories.season import recalc_season_stats
from app.commands.categories.season import season_create
from app.commands.categories.season import season_end
from app.commands.categories.season import season_list
from app.commands.categories.season import season_schedule
from app.commands.categories.season import season_start
from app.commands.categories.season import seasons
from app.commands.categories.season import seasons_all
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

                        assert result is not None
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

            assert result is not None
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

                assert result is not None
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

                    assert result is not None
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

                assert result is not None
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

                    assert result is not None
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

                assert result is not None
                assert "not active" in result


class TestRecalcSeasonStats:
    """Test recalc season stats command."""

    @pytest.mark.asyncio
    async def test_recalc_all(self, mock_context):
        """Test recalculating stats for all seasons."""
        mock_context.args = ["all"]

        # Set up the database fetch_all mock on the context object
        mock_context.state.services.database.fetch_all = AsyncMock(
            return_value=[
                {"id": 1, "name": "Season1"},
                {"id": 2, "name": "Season2"},
            ]
        )

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.bg_loops.calculate_season_stats_for_all_users",
                AsyncMock(),
            ):
                with patch(
                    "app.commands.categories.season.asyncio.create_task",
                ):
                    result = await recalc_season_stats.callback(mock_context)

                    assert result is not None
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

                        assert result is not None
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

                assert result is not None
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

                assert result is not None
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

                    assert result is not None
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

                assert result is not None
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

            assert result is not None
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

            assert result is not None
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

            assert result is not None
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

                assert result is not None
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

            assert result is not None
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

            assert result is not None
            assert "Switched to all-time view" in result
            assert mock_player.preferred_lb_view == "all_time"


class TestSeasonCreateEdgeCases:
    """Test season create command edge cases."""

    @pytest.mark.asyncio
    async def test_create_invalid_schedule_id(self, mock_context):
        """Test creating a season with non-numeric schedule ID."""
        mock_context.args = ["TestSeason", "abc"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_create.callback(mock_context)

            assert result is not None
            assert "Schedule ID must be a number" in result

    @pytest.mark.asyncio
    async def test_create_no_provider(self, mock_context):
        """Test creating a season with no provider for schedule type."""
        mock_context.args = ["TestSeason", "1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_schedule_by_id",
                AsyncMock(
                    return_value={
                        "id": 1,
                        "schedule_type": "unknown_type",
                        "config": {},
                    }
                ),
            ):
                with patch(
                    "app.schedule_types.get_provider_for_schedule_type",
                    Mock(return_value=None),
                ):
                    result = await season_create.callback(mock_context)

                    assert result is not None
                    assert "No provider found" in result


class TestSeasonStartEdgeCases:
    """Test season start command edge cases."""

    @pytest.mark.asyncio
    async def test_start_invalid_syntax(self, mock_context):
        """Test starting a season with invalid syntax."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_start.callback(mock_context)

            assert result is not None
            assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_start_non_numeric(self, mock_context):
        """Test starting a season with non-numeric ID."""
        mock_context.args = ["abc"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_start.callback(mock_context)

            assert result is not None
            assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_start_not_found(self, mock_context):
        """Test starting a non-existent season."""
        mock_context.args = ["999"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(return_value=None),
            ):
                result = await season_start.callback(mock_context)

                assert result is not None
                assert "Season not found" in result


class TestSeasonEndEdgeCases:
    """Test season end command edge cases."""

    @pytest.mark.asyncio
    async def test_end_invalid_syntax(self, mock_context):
        """Test ending a season with invalid syntax."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_end.callback(mock_context)

            assert result is not None
            assert "Invalid syntax" in result

    @pytest.mark.asyncio
    async def test_end_not_found(self, mock_context):
        """Test ending a non-existent season."""
        mock_context.args = ["999"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(return_value=None),
            ):
                result = await season_end.callback(mock_context)

                assert result is not None
                assert "Season not found" in result


class TestSeasonScheduleEdgeCases:
    """Test season schedule command edge cases."""

    @pytest.mark.asyncio
    async def test_schedule_create_invalid_type(self, mock_context):
        """Test creating a schedule with invalid type."""
        mock_context.args = ["create", "TestSchedule", "invalid_type"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.schedule_types.get_provider_for_schedule_type",
                Mock(return_value=None),
            ):
                result = await season_schedule.callback(mock_context)

                assert result is not None
                assert "No provider found" in result

    @pytest.mark.asyncio
    async def test_schedule_invalid_action(self, mock_context):
        """Test schedule with invalid action."""
        mock_context.args = ["invalid"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_schedule.callback(mock_context)

            assert result is not None
            assert "Invalid action" in result

    @pytest.mark.asyncio
    async def test_schedule_create_missing_args(self, mock_context):
        """Test creating a schedule with missing arguments."""
        mock_context.args = ["create", "TestSchedule"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_schedule.callback(mock_context)

            assert result is not None
            assert "Invalid syntax" in result


class TestSeasonsEdgeCases:
    """Test seasons command edge cases."""

    @pytest.mark.asyncio
    async def test_seasons_invalid_action(self, mock_context):
        """Test seasons with invalid action."""
        mock_context.args = ["invalid_action"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await seasons.callback(mock_context)

            assert result is not None
            # Should show help or error

    @pytest.mark.asyncio
    async def test_seasons_view_nonexistent(self, mock_context):
        """Test viewing a non-existent season."""
        mock_context.args = ["999"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(return_value=None),
            ):
                result = await seasons.callback(mock_context)

                assert result is not None
                assert "not found" in result.lower() or "Season" in result


class TestRecalcSeasonStatsEdgeCases:
    """Test recalc season stats command edge cases."""

    @pytest.mark.asyncio
    async def test_recalc_invalid_syntax(self, mock_context):
        """Test recalc with invalid syntax."""
        mock_context.args = ["invalid"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await recalc_season_stats.callback(mock_context)

            assert result is not None
            assert (
                "Invalid" in result
                or "usage" in result.lower()
                or "must be" in result.lower()
            )

    @pytest.mark.asyncio
    async def test_recalc_season_not_found(self, mock_context):
        """Test recalculating a non-existent season."""
        mock_context.args = ["999"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(return_value=None),
            ):
                result = await recalc_season_stats.callback(mock_context)

                assert result is not None
                assert "not found" in result.lower()


class TestIsSeasonsEnabled:
    """Test _is_seasons_enabled helper function."""

    @pytest.mark.asyncio
    async def test_seasons_enabled_true(self, mock_context):
        """Test when seasons are enabled."""
        from app.commands.categories.season import _is_seasons_enabled

        mock_context.state.services.database.fetch_val = AsyncMock(return_value="1")

        result = await _is_seasons_enabled(mock_context.state.services.database)

        assert result is True

    @pytest.mark.asyncio
    async def test_seasons_enabled_false(self, mock_context):
        """Test when seasons are disabled."""
        from app.commands.categories.season import _is_seasons_enabled

        mock_context.state.services.database.fetch_val = AsyncMock(return_value="0")

        result = await _is_seasons_enabled(mock_context.state.services.database)

        assert result is False

    @pytest.mark.asyncio
    async def test_seasons_enabled_exception(self, mock_context):
        """Test when database query raises exception."""
        from app.commands.categories.season import _is_seasons_enabled

        mock_context.state.services.database.fetch_val = AsyncMock(
            side_effect=Exception("DB error")
        )

        result = await _is_seasons_enabled(mock_context.state.services.database)

        assert result is False


class TestSeasonStartDisabled:
    """Test season start when seasons are disabled."""

    @pytest.mark.asyncio
    async def test_start_disabled(self, mock_context):
        """Test starting a season when seasons are disabled."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=False),
        ):
            result = await season_start.callback(mock_context)

            assert result is None


class TestSeasonEndDisabled:
    """Test season end when seasons are disabled."""

    @pytest.mark.asyncio
    async def test_end_disabled(self, mock_context):
        """Test ending a season when seasons are disabled."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=False),
        ):
            result = await season_end.callback(mock_context)

            assert result is None


class TestRecalcSeasonStatsDisabled:
    """Test recalc season stats when seasons are disabled."""

    @pytest.mark.asyncio
    async def test_recalc_disabled(self, mock_context):
        """Test recalc when seasons are disabled."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=False),
        ):
            result = await recalc_season_stats.callback(mock_context)

            assert result is not None
            assert "Seasons are not enabled" in result


class TestRecalcSeasonStatsNoArgs:
    """Test recalc season stats with no arguments."""

    @pytest.mark.asyncio
    async def test_recalc_no_args(self, mock_context):
        """Test recalc with no arguments."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await recalc_season_stats.callback(mock_context)

            assert result is not None
            assert "Usage" in result


class TestRecalcSeasonStatsAllEmpty:
    """Test recalc season stats for all seasons when none exist."""

    @pytest.mark.asyncio
    async def test_recalc_all_no_seasons(self, mock_context):
        """Test recalc all when no seasons exist."""
        mock_context.args = ["all"]

        mock_context.state.services.database.fetch_all = AsyncMock(
            return_value=[],
        )

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await recalc_season_stats.callback(mock_context)

            assert result is not None
            assert "No seasons found" in result


class TestRecalcSeasonStatsSingle:
    """Test recalc season stats for a single season."""

    @pytest.mark.asyncio
    async def test_recalc_single_success(self, mock_context):
        """Test recalc for a single season returns expected message."""
        mock_context.args = ["1"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_one",
                AsyncMock(return_value={"id": 1, "name": "TestSeason"}),
            ):
                result = await recalc_season_stats.callback(mock_context)

                assert result is not None
                assert "Started recalculating season 'TestSeason'" in result


class TestSeasonListDisabled:
    """Test season list when seasons are disabled."""

    @pytest.mark.asyncio
    async def test_list_disabled(self, mock_context):
        """Test listing seasons when seasons are disabled."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=False),
        ):
            result = await season_list.callback(mock_context)

            assert result is None


class TestSeasonScheduleDisabled:
    """Test season schedule when seasons are disabled."""

    @pytest.mark.asyncio
    async def test_schedule_disabled(self, mock_context):
        """Test schedule command when seasons are disabled."""
        mock_context.args = ["list"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=False),
        ):
            result = await season_schedule.callback(mock_context)

            assert result is None


class TestSeasonScheduleNoArgs:
    """Test season schedule with no arguments."""

    @pytest.mark.asyncio
    async def test_schedule_no_args(self, mock_context):
        """Test schedule command with no arguments."""
        mock_context.args = []

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            result = await season_schedule.callback(mock_context)

            assert result is not None
            assert "Invalid syntax" in result


class TestSeasonScheduleListEmpty:
    """Test season schedule list when no schedules exist."""

    @pytest.mark.asyncio
    async def test_schedule_list_empty(self, mock_context):
        """Test listing schedules when none exist."""
        mock_context.args = ["list"]

        with patch(
            "app.commands.categories.season._is_seasons_enabled",
            AsyncMock(return_value=True),
        ):
            with patch(
                "app.commands.categories.season.seasons_repo.fetch_many_schedules",
                AsyncMock(return_value=[]),
            ):
                result = await season_schedule.callback(mock_context)

                assert result is not None
                assert "No schedules found" in result


class TestSeasonsInvalidSeasonId:
    """Test seasons command with invalid season ID."""

    @pytest.mark.asyncio
    async def test_seasons_non_numeric(self, mock_context):
        """Test seasons with non-numeric argument."""
        mock_context.args = ["abc"]

        result = await seasons.callback(mock_context)

        assert result is not None
        assert "Invalid season ID" in result
