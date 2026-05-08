"""
Mappool Commands

Commands for managing tournament mappools.
"""

from __future__ import annotations

import time

import app.settings
from app.commands.base import CommandCategory
from app.commands.base import mappool_command
from app.commands.context import Context
from app.constants import regexes
from app.constants.mods import Mods
from app.objects.beatmap import Beatmap
from app.repositories import tourney_pool_maps as tourney_pool_maps_repo
from app.repositories import tourney_pools as tourney_pools_repo
from app.repositories import users as users_repo


@mappool_command(
    name="help",
    triggers=["help"],
    description="Show all documented mappool commands the player can access.",
    hidden=True,
)
async def pool_help(ctx: Context) -> str:
    """Show all documented mappool commands the player can access."""
    prefix = app.settings.COMMAND_PREFIX
    cmds = []

    # Get all mappool commands from the registry
    from app.commands import get_registry

    for cmd in get_registry().get_by_category(CommandCategory.MAPPOOL):
        if (
            not cmd.metadata.description
            or ctx.player.priv & cmd.privileges != cmd.privileges
        ):
            # no doc, or insufficient permissions.
            continue

        cmds.append(
            f"{prefix}pool {cmd.metadata.triggers[0]}: {cmd.metadata.description}"
        )

    return "\n".join(cmds)


@mappool_command(
    name="create",
    triggers=["create", "c"],
    description="Add a new mappool to the database.",
    hidden=True,
)
async def pool_create(ctx: Context) -> str:
    """Add a new mappool to the database."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !pool create <name>"

    name = ctx.args[0]

    existing_pool = await tourney_pools_repo.fetch_by_name(name)
    if existing_pool is not None:
        return "Pool already exists by that name!"

    await tourney_pools_repo.create(
        name=name,
        created_by=ctx.player.id,
    )

    return f"{name} created."


@mappool_command(
    name="delete",
    triggers=["delete", "del", "d"],
    description="Remove a mappool from the database.",
    hidden=True,
)
async def pool_delete(ctx: Context) -> str:
    """Remove a mappool from the database."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !pool delete <name>"

    name = ctx.args[0]

    existing_pool = await tourney_pools_repo.fetch_by_name(name)
    if existing_pool is None:
        return "Could not find a pool by that name!"

    await tourney_pools_repo.delete_by_id(existing_pool["id"])
    await tourney_pool_maps_repo.delete_all_in_pool(pool_id=existing_pool["id"])

    return f"{name} deleted."


@mappool_command(
    name="add",
    triggers=["add", "a"],
    description="Add a new map to a mappool in the database.",
    hidden=True,
)
async def pool_add(ctx: Context) -> str:
    """Add a new map to a mappool in the database."""
    if len(ctx.args) != 2:
        return "Invalid syntax: !pool add <name> <pick>"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    name, mods_slot = ctx.args
    mods_slot = mods_slot.upper()  # ocd
    bmap = ctx.player.last_np["bmap"]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    if len(r_match[1]) % 2 != 0:
        return "Invalid mods."

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    tourney_pool = await tourney_pools_repo.fetch_by_name(name)
    if tourney_pool is None:
        return "Could not find a pool by that name!"

    tourney_pool_maps = await tourney_pool_maps_repo.fetch_many(
        pool_id=tourney_pool["id"],
    )
    for pool_map in tourney_pool_maps:
        if mods == pool_map["mods"] and slot == pool_map["slot"]:
            pool_beatmap = await Beatmap.from_bid(pool_map["map_id"])
            if pool_beatmap is None:
                raise ValueError("Pool beatmap not found")
            return f"{mods_slot} is already {pool_beatmap.embed}!"

        if pool_map["map_id"] == bmap.id:
            return f"{bmap.embed} is already in the pool!"

    await tourney_pool_maps_repo.create(
        map_id=bmap.id,
        pool_id=tourney_pool["id"],
        mods=mods,
        slot=slot,
    )

    return f"{bmap.embed} added to {name} as {mods_slot}."


@mappool_command(
    name="remove",
    triggers=["remove", "rm", "r"],
    description="Remove a map from a mappool in the database.",
    hidden=True,
)
async def pool_remove(ctx: Context) -> str:
    """Remove a map from a mappool in the database."""
    if len(ctx.args) != 2:
        return "Invalid syntax: !pool remove <name> <pick>"

    name, mods_slot = ctx.args
    mods_slot = mods_slot.upper()  # ocd

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    tourney_pool = await tourney_pools_repo.fetch_by_name(name)
    if tourney_pool is None:
        return "Could not find a pool by that name!"

    map_pick = await tourney_pool_maps_repo.fetch_by_pool_and_pick(
        pool_id=tourney_pool["id"],
        mods=mods,
        slot=slot,
    )
    if map_pick is None:
        return f"Found no {mods_slot} pick in the pool."

    await tourney_pool_maps_repo.delete_map_from_pool(
        map_pick["pool_id"],
        map_pick["map_id"],
    )

    return f"{mods_slot} removed from {name}."


@mappool_command(
    name="list",
    triggers=["list", "l"],
    description="List all existing mappools information.",
    hidden=True,
)
async def pool_list(ctx: Context) -> str:
    """List all existing mappools information."""
    tourney_pools = await tourney_pools_repo.fetch_many(page=None, page_size=None)
    if not tourney_pools:
        return "There are currently no pools!"

    pool_lines = [f"Mappools ({len(tourney_pools)})"]

    for pool in tourney_pools:
        created_by = await users_repo.fetch_one(id=pool["created_by"])
        if created_by is None:
            # Log error but continue
            continue

        pool_lines.append(
            f"[{pool['created_at']:%Y-%m-%d}] {pool['name']}, by {created_by['name']}.",
        )

    return "\n".join(pool_lines)


@mappool_command(
    name="info",
    triggers=["info", "i"],
    description="Get all information for a specific mappool.",
    hidden=True,
)
async def pool_info(ctx: Context) -> str:
    """Get all information for a specific mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !pool info <name>"

    name = ctx.args[0]

    tourney_pool = await tourney_pools_repo.fetch_by_name(name)
    if tourney_pool is None:
        return "Could not find a pool by that name!"

    _time = tourney_pool["created_at"].strftime("%H:%M:%S%p")
    _date = tourney_pool["created_at"].strftime("%Y-%m-%d")
    datetime_fmt = f"Created at {_time} on {_date}"
    lines = [
        f"{tourney_pool['id']}. {tourney_pool['name']}, by {tourney_pool['created_by']} | {datetime_fmt}.",
    ]

    for tourney_map in sorted(
        await tourney_pool_maps_repo.fetch_many(pool_id=tourney_pool["id"]),
        key=lambda x: (repr(Mods(x["mods"])), x["slot"]),
    ):
        bmap = await Beatmap.from_bid(tourney_map["map_id"])
        if bmap is None:
            continue
        lines.append(
            f"{Mods(tourney_map['mods'])!r}{tourney_map['slot']}: {bmap.embed}",
        )

    return "\n".join(lines)
