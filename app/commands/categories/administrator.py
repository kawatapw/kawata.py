"""
Administrator Commands

Commands for administrator role.
"""

from __future__ import annotations

import os
import signal
import time
from typing import TYPE_CHECKING
from typing import cast

import timeago
from pytimeparse.timeparse import timeparse

import app.state
from app.commands.base import administrator_command
from app.commands.base import developer_command
from app.commands.context import Context
from app.constants.privileges import Privileges
from app.packets import notification
from app.packets import switch_tournament_server
from app.repositories import clans as clans_repo

# Define SHORTHAND_REASONS
# Includes both classic shorthand codes and human-readable keywords
SHORTHAND_REASONS = {
    # Classic codes (from old bancho.py)
    "aa": "having their appeal accepted",
    "cc": "using a modified osu! client",
    "3p": "using 3rd party programs",
    "rx": "using 3rd party programs (relax)",
    "tw": "using 3rd party programs (timewarp)",
    "au": "using 3rd party programs (auto play)",
    # Human-readable keywords (from new system)
    "appeal": "appeal accepted",
    "cheat": "cheating",
    "bad": "bad behavior",
    "spam": "spamming",
}

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop


@administrator_command(
    name="user",
    triggers=["user", "u"],
    description="Return general information about a given user.",
    hidden=True,
)
async def user(ctx: Context) -> str:
    """Return general information about a given user."""
    if not ctx.args:
        # no username specified, use ctx.player
        player = ctx.player
    else:
        # username given, fetch the player
        maybe_player = await ctx.state.sessions.players.from_cache_or_sql(
            name=" ".join(ctx.args),
        )

        if maybe_player is None:
            return "Player not found."

        player = maybe_player

    priv_list = [
        priv.name
        for priv in Privileges
        if priv.value != 0 and player.priv & priv.value == priv.value
    ][::-1]
    if player.last_np is not None and time.time() < player.last_np["timeout"]:
        last_np = player.last_np["bmap"].embed
    else:
        last_np = None

    if player.is_online and player.client_details is not None:
        osu_version = player.client_details.osu_version.date.isoformat()
    else:
        osu_version = "Unknown"

    donator_info = (
        f"True (ends {timeago.format(player.donor_end)})"
        if player.priv & Privileges.DONATOR != 0
        else "False"
    )

    user_clan = (
        await clans_repo.fetch_one(id=player.clan_id)
        if player.clan_id is not None
        else None
    )
    display_name = (
        f"[{user_clan['tag']}] {player.name}" if user_clan is not None else player.name
    )

    return "\n".join(
        (
            f"[{'Bot' if player.is_bot_client else 'Player'}] {display_name} ({player.id})",
            f"Privileges: {priv_list}",
            f"Donator: {donator_info}",
            f"Channels: {[c.real_name for c in player.channels]}",
            f"Logged in: {timeago.format(player.login_time)}",
            f"Last server interaction: {timeago.format(player.last_recv_time)}",
            f"osu! build: {osu_version} | Tourney: {player.is_tourney_client}",
            f"Silenced: {player.silenced} | Spectating: {player.spectating}",
            f"Last /np: {last_np}",
            f"Recent score: {player.recent_score}",
            f"Match: {player.match}",
            f"Spectators: {player.spectators}",
        ),
    )


@administrator_command(
    name="restrict",
    description="Restrict a specified player's account, with a reason.",
    hidden=True,
)
async def restrict(ctx: Context) -> str:
    """Restrict a specified player's account, with a reason."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !restrict <name> <reason>"

    # find any user matching (including offline).
    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    if target.restricted:
        return f"{target} is already restricted!"

    reason = " ".join(ctx.args[1:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await target.restrict(admin=ctx.player, reason=reason)

    # refresh their client state
    if target.is_online:
        target.logout()

    return f"{target} was restricted."


@administrator_command(
    name="unrestrict",
    description="Unrestrict a specified player's account, with a reason.",
    hidden=True,
)
async def unrestrict(ctx: Context) -> str:
    """Unrestrict a specified player's account, with a reason."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !unrestrict <name> <reason>"

    # find any user matching (including offline).
    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    if not target.restricted:
        return f"{target} is not restricted!"

    reason = " ".join(ctx.args[1:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await target.unrestrict(ctx.player, reason)

    # refresh their client state
    if target.is_online:
        target.logout()

    return f"{target} was unrestricted."


@administrator_command(
    name="alert",
    description="Send a notification to all players.",
    hidden=True,
)
async def alert(ctx: Context) -> str:
    """Send a notification to all players."""
    if len(ctx.args) < 1:
        return "Invalid syntax: !alert <msg>"

    notif_txt = " ".join(ctx.args)

    ctx.state.sessions.players.enqueue(notification(notif_txt))
    return "Alert sent."


@administrator_command(
    name="alertuser",
    triggers=["alertuser", "alertu"],
    description="Send a notification to a specified player by name.",
    hidden=True,
)
async def alertuser(ctx: Context) -> str:
    """Send a notification to a specified player by name."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !alertu <name> <msg>"

    target = ctx.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    notif_txt = " ".join(ctx.args[1:])

    target.enqueue(notification(notif_txt))
    return "Alert sent."


# NOTE: this is pretty useless since it doesn't switch anything other
# than the c[e4].ppy.sh domains; it exists on bancho as a tournament
# server switch mechanism, perhaps we could leverage this in the future.


@administrator_command(
    name="switchserv",
    description="Switch your client's internal endpoints to a specified IP address.",
    hidden=True,
)
async def switchserv(ctx: Context) -> str:
    """Switch your client's internal endpoints to a specified IP address."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !switch <endpoint>"

    new_bancho_ip = ctx.args[0]

    ctx.player.enqueue(switch_tournament_server(new_bancho_ip))
    return "Have a nice journey.."


@administrator_command(
    name="shutdown",
    description="Toggle the developer's stealth, allowing them to be hidden.",
)
async def shutdown(ctx: Context) -> str | None:
    """Gracefully shutdown the server."""
    if ctx.args:  # shutdown after a delay
        delay = timeparse(ctx.args[0])
        if not delay:
            return "Invalid timespan."

        if delay < 15:
            return "Minimum delay is 15 seconds."

        if len(ctx.args) > 1:
            # alert all online players of the reboot.
            alert_msg = (
                f"The server will {ctx.trigger} in {ctx.args[0]}.\n\n"
                f"Reason: {' '.join(ctx.args[1:])}"
            )

            ctx.state.sessions.players.enqueue(notification(alert_msg))

        cast("AbstractEventLoop", app.state.loop).call_later(
            delay, os.kill, os.getpid(), signal.SIGTERM
        )
        return f"Enqueued {ctx.trigger}."
    # shutdown immediately
    os.kill(os.getpid(), signal.SIGTERM)
    return "Process killed"


""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""


@developer_command(
    name="stealth",
    description="Toggle the developer's stealth, allowing them to be hidden.",
    hidden=True,
)
async def stealth(ctx: Context) -> str:
    """Toggle the developer's stealth, allowing them to be hidden."""
    # NOTE: this command is a large work in progress and currently
    # half works; eventually it will be moved to the Admin level.
    ctx.player.stealth = not ctx.player.stealth

    return f"Stealth {'enabled' if ctx.player.stealth else 'disabled'}."
