"""
Season Commands

Commands for managing seasons.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.commands.base import season_command
from app.commands.context import Context
from app.repositories import seasons as seasons_repo
from app.repositories import users as users_repo

if TYPE_CHECKING:
    pass


async def _is_seasons_enabled(database: Any) -> bool:
    """Check if seasons are enabled via server_data."""
    try:
        enabled = await database.fetch_val(
            "SELECT value FROM server_data WHERE type = 'seasons_enabled'",
        )
        return bool(enabled == "1")
    except Exception:
        return False


@season_command(
    name="create",
    description="Create a new season.",
    hidden=True,
)
async def season_create(ctx: Context) -> str | None:
    """Create a new season."""
    if not await _is_seasons_enabled(ctx.state.services.database):
        return None

    if len(ctx.args) < 2:
        return "Invalid syntax: !season create <name> <schedule_id>"

    name = ctx.args[0]
    if not ctx.args[1].isdecimal():
        return "Schedule ID must be a number."

    schedule_id = int(ctx.args[1])

    # verify schedule exists
    schedule = await seasons_repo.fetch_schedule_by_id(schedule_id)
    if schedule is None:
        return "Schedule not found."

    # get provider for schedule type
    from app.schedule_types import get_provider_for_schedule_type

    provider = get_provider_for_schedule_type(schedule["schedule_type"])
    if provider is None:
        return f"No provider found for schedule type: {schedule['schedule_type']}"

    # calculate season dates based on schedule
    current_time = datetime.now()
    start_date, end_date = provider.calculate_next_season(
        schedule["schedule_type"],
        current_time,
        schedule["config"],
    )

    # create season
    season = await seasons_repo.create(
        name=name,
        schedule_id=schedule_id,
        start_date=start_date,
        end_date=end_date,
    )

    return f"Season '{name}' created with ID {season['id']}."


@season_command(
    name="start",
    description="Start/activate a season.",
    hidden=True,
)
async def season_start(ctx: Context) -> str | None:
    """Start/activate a season."""
    if not await _is_seasons_enabled(ctx.state.services.database):
        return None

    if len(ctx.args) != 1 or not ctx.args[0].isdecimal():
        return "Invalid syntax: !season start <season_id>"

    season_id = int(ctx.args[0])

    season = await seasons_repo.fetch_one(id=season_id)
    if season is None:
        return "Season not found."

    if season["is_active"]:
        return "Season is already active."

    await seasons_repo.activate(season_id)
    return f"Season '{season['name']}' activated."


@season_command(
    name="end",
    description="End/deactivate a season.",
    hidden=True,
)
async def season_end(ctx: Context) -> str | None:
    """End/deactivate a season."""
    if not await _is_seasons_enabled(ctx.state.services.database):
        return None

    if len(ctx.args) != 1 or not ctx.args[0].isdecimal():
        return "Invalid syntax: !season end <season_id>"

    season_id = int(ctx.args[0])

    season = await seasons_repo.fetch_one(id=season_id)
    if season is None:
        return "Season not found."

    if not season["is_active"]:
        return "Season is not active."

    await seasons_repo.deactivate(season_id)
    return f"Season '{season['name']}' deactivated."


@season_command(
    name="recalc",
    description="Recalculate stats for a season (or all seasons).",
    hidden=True,
)
async def recalc_season_stats(ctx: Context) -> str | None:
    """Recalculate stats for a season (or all seasons).

    Usage:
        !season recalc <season_id> - Recalculate stats for a specific season
        !season recalc all         - Recalculate stats for all seasons
    """
    if not await _is_seasons_enabled(ctx.state.services.database):
        return "Seasons are not enabled."

    if not ctx.args:
        return "Usage: !season recalc <season_id> or !season recalc all"

    from app.bg_loops import calculate_season_stats_for_all_users

    player = ctx.player

    if ctx.args[0].lower() == "all":
        all_seasons = await ctx.state.services.database.fetch_all(
            "SELECT id, name FROM seasons ORDER BY id",
        )
        if not all_seasons:
            return "No seasons found."

        async def _recalc_all() -> None:
            for s in all_seasons:
                player.send_bot(f"Recalculating season '{s['name']}' ({s['id']})...")
                await calculate_season_stats_for_all_users(s["id"])
            player.send_bot(f"Done! Recalculated stats for {len(all_seasons)} seasons.")

        # Background task - intentionally not awaited
        asyncio.create_task(_recalc_all())  # type: ignore[unused-awaitable]
        return f"Started recalculating {len(all_seasons)} seasons in background. You'll get a message when done."

    if not ctx.args[0].isdecimal():
        return "Season ID must be a number, or 'all'."

    season_id = int(ctx.args[0])
    season = await seasons_repo.fetch_one(id=season_id)
    if season is None:
        return "Season not found."

    async def _recalc_one() -> None:
        await calculate_season_stats_for_all_users(season_id)
        player.send_bot(f"Done! Recalculated stats for season '{season['name']}'.")

        # Background task - intentionally not awaited
        asyncio.create_task(_recalc_one())  # type: ignore[unused-awaitable]

    return f"Started recalculating season '{season['name']}' in background. You'll get a message when done."


@season_command(
    name="list",
    description="List all seasons.",
    hidden=True,
)
async def season_list(ctx: Context) -> str | None:
    """List all seasons."""
    if not await _is_seasons_enabled(ctx.state.services.database):
        return None

    seasons = await seasons_repo.fetch_many(page=None, page_size=None)
    if not seasons:
        return "No seasons found."

    msg = [f"Seasons ({len(seasons)} total):"]
    for season in seasons:
        status = "Active" if season["is_active"] else "Inactive"
        msg.append(
            f"[{status}] {season['id']}. {season['name']} ({season['start_date']:%Y-%m-%d} to {season['end_date']:%Y-%m-%d})",
        )

    return "\n".join(msg)


@season_command(
    name="schedule",
    description="Manage season schedules.",
    hidden=True,
)
async def season_schedule(ctx: Context) -> str | None:
    """Manage season schedules."""
    if not await _is_seasons_enabled(ctx.state.services.database):
        return None

    if not ctx.args:
        return "Invalid syntax: !season schedule <create/list/info>"

    action = ctx.args[0].lower()

    if action == "create":
        if len(ctx.args) < 3:
            return "Invalid syntax: !season schedule create <name> <schedule_type>"

        name = ctx.args[1]
        schedule_type = ctx.args[2]

        # get provider for schedule type to validate and get default config
        from app.schedule_types import get_provider_for_schedule_type

        provider = get_provider_for_schedule_type(schedule_type)
        if provider is None:
            return f"No provider found for schedule type: {schedule_type}"

        # get default config from provider schema
        config_schema = provider.get_config_schema(schedule_type)
        default_config = {}
        if "properties" in config_schema:
            for prop_name, prop_schema in config_schema["properties"].items():
                if "default" in prop_schema:
                    default_config[prop_name] = prop_schema["default"]

        # create schedule
        schedule = await seasons_repo.create_schedule(
            name=name,
            schedule_type=schedule_type,
            config=default_config,
        )

        return f"Schedule '{name}' created with ID {schedule['id']}."

    elif action == "list":
        schedules = await seasons_repo.fetch_many_schedules()
        if not schedules:
            return "No schedules found."

        msg = [f"Schedules ({len(schedules)} total):"]
        for schedule in schedules:
            msg.append(
                f"{schedule['id']}. {schedule['name']} ({schedule['schedule_type']})",
            )

        return "\n".join(msg)

    else:
        return "Invalid action. Use: create, list, or info"


@season_command(
    name="toggle",
    description="Toggle between all-time and seasonal view, or view specific season stats.",
)
async def seasons(ctx: Context) -> str | None:
    """Toggle between all-time and seasonal view, or view specific season stats.

    Usage:
        !seasons - Toggle between all-time and seasonal view
        !seasons <season_id> - View stats for a specific season
        !seasons all - Switch to all-time view
    """
    if not ctx.args:
        # Toggle between all-time and seasonal view
        if ctx.player.preferred_lb_view == "all_time":
            ctx.player.preferred_lb_view = "seasonal"
            await users_repo.partial_update(
                id=ctx.player.id,
                preferred_lb_view="seasonal",
            )
            return "Switched to seasonal view."
        else:
            ctx.player.preferred_lb_view = "all_time"
            await users_repo.partial_update(
                id=ctx.player.id,
                preferred_lb_view="all_time",
            )
            return "Switched to all-time view."

    # Handle specific season ID or "all"
    arg = ctx.args[0].lower()

    if arg == "all":
        # Switch to all-time view
        ctx.player.preferred_lb_view = "all_time"
        ctx.player.selected_season_id = None
        await users_repo.partial_update(
            id=ctx.player.id,
            preferred_lb_view="all_time",
        )
        return "Switched to all-time view."

    # Try to parse as season ID
    try:
        season_id = int(arg)
    except ValueError:
        return "Invalid season ID. Use !seasons <season_id> or !seasons all."

    # Verify season exists
    season = await seasons_repo.fetch_one(id=season_id)
    if not season:
        return f"Season with ID {season_id} not found."

    # Set the player's selected season
    ctx.player.preferred_lb_view = "seasonal"
    ctx.player.selected_season_id = season_id
    await users_repo.partial_update(
        id=ctx.player.id,
        preferred_lb_view="seasonal",
    )

    return f"Switched to viewing season: {season['name']} (ID: {season_id})"


@season_command(
    name="all",
    description="Switch to all-time view.",
)
async def seasons_all(ctx: Context) -> str | None:
    """Switch to all-time view."""
    ctx.player.preferred_lb_view = "all_time"
    await users_repo.partial_update(
        id=ctx.player.id,
        preferred_lb_view="all_time",
    )
    return "Switched to all-time view."
