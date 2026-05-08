"""
Clan Commands

Commands for managing clans.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.commands.base import clan_command
from app.commands.context import Context
from app.constants.privileges import ClanPrivileges
from app.repositories import clans as clans_repo
from app.repositories import users as users_repo

if TYPE_CHECKING:
    pass


@clan_command(
    name="help",
    triggers=["help", "h"],
    description="Show all documented clan commands the player can access.",
)
async def clan_help(ctx: Context) -> str:
    """Show all documented clan commands the player can access."""
    prefix = ctx.settings.COMMAND_PREFIX if hasattr(ctx, 'settings') and ctx.settings else "!"
    cmds = []

    # Get all clan commands from the registry
    from app.commands import registry

    for cmd in registry.get_by_category("clan"):
        if (
            not cmd.metadata.description
            or ctx.player.priv & cmd.privileges != cmd.privileges
        ):
            # no doc, or insufficient permissions.
            continue

        cmds.append(
            f"{prefix}clan {cmd.metadata.triggers[0]}: {cmd.metadata.description}"
        )

    return "\n".join(cmds)


@clan_command(
    name="create",
    triggers=["create", "c"],
    description="Create a clan with a given tag & name.",
)
async def clan_create(ctx: Context) -> str:
    """Create a clan with a given tag & name."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !clan create <tag> <name>"

    tag = ctx.args[0].upper()
    if not 1 <= len(tag) <= 6:
        return "Clan tag may be 1-6 characters long."

    name = " ".join(ctx.args[1:])
    if not 2 <= len(name) <= 16:
        return "Clan name may be 2-16 characters long."

    if ctx.player.clan_id:
        clan = await clans_repo.fetch_one(id=ctx.player.clan_id)
        if clan:
            clan_display_name = f"[{clan['tag']}] {clan['name']}"
            return f"You're already a member of {clan_display_name}!"

    if await clans_repo.fetch_one(name=name):
        return "That name has already been claimed by another clan."

    if await clans_repo.fetch_one(tag=tag):
        return "That tag has already been claimed by another clan."

    # add clan to sql
    new_clan = await clans_repo.create(
        name=name,
        tag=tag,
        owner=ctx.player.id,
    )

    # set owner's clan & clan priv (cache & sql)
    ctx.player.clan_id = new_clan["id"]
    ctx.player.clan_priv = ClanPrivileges.Owner

    await users_repo.partial_update(
        ctx.player.id,
        clan_id=new_clan["id"],
        clan_priv=ClanPrivileges.Owner,
    )

    # announce clan creation
    announce_chan = ctx.state.sessions.channels.get_by_name("#announce")
    clan_display_name = f"[{new_clan['tag']}] {new_clan['name']}"

    if announce_chan:
        msg = f"\x01ACTION founded {clan_display_name}."
        announce_chan.send(msg, sender=ctx.player, to_self=True)

    return f"{clan_display_name} founded."


@clan_command(
    name="disband",
    triggers=["disband", "delete", "d"],
    description="Disband a clan (admins may disband others clans).",
)
async def clan_disband(ctx: Context) -> str:
    """Disband a clan (admins may disband others clans)."""
    if ctx.args:
        # disband a specified clan by tag
        if ctx.player not in ctx.state.sessions.players.staff:
            return "Only staff members may disband the clans of others."

        clan = await clans_repo.fetch_one(tag=" ".join(ctx.args).upper())
        if not clan:
            return "Could not find a clan by that tag."
    else:
        if ctx.player.clan_id is None:
            return "You're not a member of a clan!"

        # disband the player's clan
        clan = await clans_repo.fetch_one(id=ctx.player.clan_id)
        if not clan:
            return "You're not a member of a clan!"

    await clans_repo.delete_one(clan["id"])

    # remove all members from the clan
    clan_member_ids = [
        clan_member["id"]
        for clan_member in await users_repo.fetch_many(clan_id=clan["id"])
    ]
    for member_id in clan_member_ids:
        await users_repo.partial_update(member_id, clan_id=0, clan_priv=0)

        member = ctx.state.sessions.players.get(id=member_id)
        if member:
            member.clan_id = None
            member.clan_priv = None

    # announce clan disbanding
    announce_chan = ctx.state.sessions.channels.get_by_name("#announce")
    clan_display_name = f"[{clan['tag']}] {clan['name']}"
    if announce_chan:
        msg = f"\x01ACTION disbanded {clan_display_name}."
        announce_chan.send(msg, sender=ctx.player, to_self=True)

    return f"{clan_display_name} disbanded."


@clan_command(
    name="info",
    triggers=["info", "i"],
    description="Lookup information of a clan by tag.",
)
async def clan_info(ctx: Context) -> str:
    """Lookup information of a clan by tag."""
    if not ctx.args:
        return "Invalid syntax: !clan info <tag>"

    clan = await clans_repo.fetch_one(tag=" ".join(ctx.args).upper())
    if not clan:
        return "Could not find a clan by that tag."

    clan_display_name = f"[{clan['tag']}] {clan['name']}"
    msg = [f"{clan_display_name} | Founded {clan['created_at']:%b %d, %Y}."]

    # get members privs from sql
    clan_members = await users_repo.fetch_many(clan_id=clan["id"])
    for member in sorted(clan_members, key=lambda m: m["clan_priv"], reverse=True):
        priv_str = ("Member", "Officer", "Owner")[member["clan_priv"] - 1]
        msg.append(f"[{priv_str}] {member['name']}")

    return "\n".join(msg)


@clan_command(
    name="leave",
    description="Leaves the clan you're in.",
)
async def clan_leave(ctx: Context) -> str:
    """Leaves the clan you're in."""
    if not ctx.player.clan_id:
        return "You're not in a clan."
    elif ctx.player.clan_priv == ClanPrivileges.Owner:
        return "You must transfer your clan's ownership before leaving it. Alternatively, you can use !clan disband."

    clan = await clans_repo.fetch_one(id=ctx.player.clan_id)
    if not clan:
        return "You're not in a clan."

    clan_members = await users_repo.fetch_many(clan_id=clan["id"])

    await users_repo.partial_update(ctx.player.id, clan_id=0, clan_priv=0)
    ctx.player.clan_id = None
    ctx.player.clan_priv = None

    clan_display_name = f"[{clan['tag']}] {clan['name']}"

    if not clan_members:
        # no members left, disband clan
        await clans_repo.delete_one(clan["id"])

        # announce clan disbanding
        announce_chan = ctx.state.sessions.channels.get_by_name("#announce")
        if announce_chan:
            msg = f"\x01ACTION disbanded {clan_display_name}."
            announce_chan.send(msg, sender=ctx.player, to_self=True)

    return f"You have successfully left {clan_display_name}."


# TODO: !clan inv, !clan join, !clan leave


@clan_command(
    name="list",
    triggers=["list", "l"],
    description="List all existing clans' information.",
)
async def clan_list(ctx: Context) -> str:
    """List all existing clans' information."""
    if ctx.args:
        if len(ctx.args) != 1 or not ctx.args[0].isdecimal():
            return "Invalid syntax: !clan list (page)"
        else:
            offset = 25 * int(ctx.args[0])
    else:
        offset = 0

    all_clans = await clans_repo.fetch_many(page=None, page_size=None)
    num_clans = len(all_clans)
    if offset >= num_clans:
        return "No clans found."

    msg = [f"bancho.py clans listing ({num_clans} total)."]

    for idx, clan in enumerate(all_clans, offset):
        clan_display_name = f"[{clan['tag']}] {clan['name']}"
        msg.append(f"{idx + 1}. {clan_display_name}")

    return "\n".join(msg)
