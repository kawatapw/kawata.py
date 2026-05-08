"""
Multiplayer Commands

Commands for multiplayer match management.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app import packets
from app.commands.base import CommandCategory, multiplayer_command
from app.commands.context import Context
from app.constants import regexes
from app.constants.mods import SPEED_CHANGING_MODS, Mods
from app.constants.privileges import Privileges
from app.objects.beatmap import Beatmap
from app.objects.match import (
    Match,
    MatchTeams,
    MatchTeamTypes,
    MatchWinConditions,
    SlotStatus,
)
from app.objects.player import Player
from app.repositories import tourney_pool_maps as tourney_pool_maps_repo
from app.repositories import tourney_pools as tourney_pools_repo

if TYPE_CHECKING:
    from app.objects.match import Match
    from app.objects.player import Player


def ensure_match(
    f: Callable[[Context, Match], Awaitable[str | None]],
) -> Callable[[Context], Awaitable[str | None]]:
    """Ensure player is in a match and has permission."""
    from functools import wraps

    @wraps(f)
    async def wrapper(ctx: Context) -> str | None:
        match = ctx.player.match

        # multi set is a bit of a special case,
        # as we do some additional checks.
        if match is None:
            # player not in a match
            return None

        if ctx.recipient is not match.chat:
            # message not in match channel
            return None

        if not (
            ctx.player in match.refs
            or ctx.player.priv & Privileges.TOURNEY_MANAGER
            or f is getattr(mp_help, "__wrapped__", None)
        ):
            return None

        return await f(ctx, match)

    return wrapper


@multiplayer_command(
    name="help",
    triggers=["help", "h"],
    description="Show all documented multiplayer commands the player can access.",
)
@ensure_match
async def mp_help(ctx: Context, match: Match) -> str:
    """Show all documented multiplayer commands the player can access."""
    prefix = (
        ctx.settings.COMMAND_PREFIX
        if hasattr(ctx, "settings") and ctx.settings
        else "!"
    )
    cmds = []

    from app.commands import get_registry

    for cmd in get_registry().get_by_category(CommandCategory.MULTIPLAYER):
        if (
            not cmd.metadata.description
            or ctx.player.priv & cmd.privileges != cmd.privileges
        ):
            # no doc, or insufficient permissions.
            continue

        cmds.append(
            f"{prefix}mp {cmd.metadata.triggers[0]}: {cmd.metadata.description}"
        )

    return "\n".join(cmds)


@multiplayer_command(
    name="start",
    triggers=["start", "st"],
    description="Start the current multiplayer match, with any players ready.",
)
@ensure_match
async def mp_start(ctx: Context, match: Match) -> str | None:
    """Start the current multiplayer match, with any players ready."""
    if len(ctx.args) > 1:
        return "Invalid syntax: !mp start <force/seconds>"

    # this command can be used in a few different ways;
    # !mp start: start the match now (make sure all players are ready)
    # !mp start force: start the match now (don't check for ready)
    # !mp start N: start the match in N seconds (don't check for ready)
    # !mp start cancel: cancel the current match start timer

    if not ctx.args:
        # !mp start - no arguments provided
        if match.starting is not None:
            time_remaining = int(match.starting["time"] - time.time())
            return f"Match starting in {time_remaining} seconds."

        # No timer active, check if all players are ready and start
        if any(s.status == SlotStatus.not_ready for s in match.slots):
            return "Not all players are ready (`!mp start force` to override)."

        match.start()
        return "Good luck!"

    # We have exactly one argument at this point
    if ctx.args[0].isdecimal():
        # !mp start N
        if match.starting is not None:
            time_remaining = int(match.starting["time"] - time.time())
            return f"Match starting in {time_remaining} seconds."

        # !mp start <seconds>
        duration = int(ctx.args[0])
        if not 0 < duration <= 300:
            return "Timer range is 1-300 seconds."

        def _start() -> None:
            """Remove any pending timers & start the match."""
            # remove start & alert timers
            match.starting = None

            # make sure player didn't leave the
            # match since queueing this start lol...
            if ctx.player not in {slot.player for slot in match.slots}:
                match.chat.send_bot("Player left match? (cancelled)")
                return

            match.start()
            match.chat.send_bot("Starting match.")

        def _alert_start(t: int) -> None:
            """Alert the match of the impending start."""
            match.chat.send_bot(f"Match starting in {t} seconds.")

        # add timers to our match object,
        # so we can cancel them if needed.
        match.starting = {
            "start": ctx.state.loop.call_later(duration, _start),
            "alerts": [
                ctx.state.loop.call_later(duration - t, lambda t=t: _alert_start(t))
                for t in (60, 30, 10, 5, 4, 3, 2, 1)
                if t < duration
            ],
            "time": time.time() + duration,
        }

        return f"Match will start in {duration} seconds."
    elif ctx.args[0] in ("cancel", "c"):
        # !mp start cancel
        if match.starting is None:
            return "Match timer not active!"

        match.starting["start"].cancel()
        for alert in match.starting["alerts"]:
            alert.cancel()

        match.starting = None

        return "Match timer cancelled."
    elif ctx.args[0] not in ("force", "f"):
        return "Invalid syntax: !mp start <force/seconds>"
    # !mp start force simply passes through

    match.start()
    return "Good luck!"


@multiplayer_command(
    name="abort",
    triggers=["abort", "a"],
    description="Abort the current in-progress multiplayer match.",
)
@ensure_match
async def mp_abort(ctx: Context, match: Match) -> str | None:
    """Abort the current in-progress multiplayer match."""
    if not match.in_progress:
        return "Abort what?"

    match.unready_players(expected=SlotStatus.playing)
    match.reset_players_loaded_status()

    match.in_progress = False
    match.enqueue(packets.match_abort())
    match.enqueue_state()
    return "Match aborted."


@multiplayer_command(
    name="map",
    description="Set the current match's current map by id.",
)
@ensure_match
async def mp_map(ctx: Context, match: Match) -> str | None:
    """Set the current match's current map by id."""
    if len(ctx.args) != 1 or not ctx.args[0].isdecimal():
        return "Invalid syntax: !mp map <beatmapid>"

    map_id = int(ctx.args[0])

    if map_id == match.map_id:
        return "Map already selected."

    bmap = await Beatmap.from_bid(map_id)
    if not bmap:
        return "Beatmap not found."

    match.map_id = bmap.id
    match.map_md5 = bmap.md5
    match.map_name = bmap.full_name

    match.mode = bmap.mode

    match.enqueue_state()
    return f"Selected: {bmap.embed}."


@multiplayer_command(
    name="mods",
    description="Set the current match's mods, from string form.",
)
@ensure_match
async def mp_mods(ctx: Context, match: Match) -> str | None:
    """Set the current match's mods, from string form."""
    if len(ctx.args) != 1 or len(ctx.args[0]) % 2 != 0:
        return "Invalid syntax: !mp mods <mods>"

    mods = Mods.from_modstr(ctx.args[0])
    mods = mods.filter_invalid_combos(match.mode.as_vanilla)

    if match.freemods:
        if ctx.player is match.host:
            # allow host to set speed-changing mods.
            match.mods = mods & SPEED_CHANGING_MODS

        # set slot mods
        slot = match.get_slot(ctx.player)
        assert slot is not None

        slot.mods = mods & ~SPEED_CHANGING_MODS
    else:
        # not freemods, set match mods.
        match.mods = mods

    match.enqueue_state()
    return "Match mods updated."


@multiplayer_command(
    name="freemods",
    triggers=["freemods", "fm", "fmods"],
    description="Toggle freemods status for the match.",
)
@ensure_match
async def mp_freemods(ctx: Context, match: Match) -> str | None:
    """Toggle freemods status for the match."""
    if len(ctx.args) != 1 or ctx.args[0] not in ("on", "off"):
        return "Invalid syntax: !mp freemods <on/off>"

    if ctx.args[0] == "on":
        # central mods -> all players mods.
        match.freemods = True

        for s in match.slots:
            if s.player is not None:
                # the slot takes any non-speed
                # changing mods from the match.
                s.mods = match.mods & ~SPEED_CHANGING_MODS

        match.mods &= SPEED_CHANGING_MODS
    else:
        # host mods -> central mods.
        match.freemods = False

        host_slot = match.get_host_slot()
        assert host_slot is not None

        # the match keeps any speed-changing mods,
        # and also takes any mods the host has enabled.
        match.mods &= SPEED_CHANGING_MODS
        match.mods |= host_slot.mods

        for s in match.slots:
            if s.player is not None:
                s.mods = Mods.NOMOD

    match.enqueue_state()
    return "Match freemod status updated."


@multiplayer_command(
    name="host",
    description="Set the current match's current host by id.",
)
@ensure_match
async def mp_host(ctx: Context, match: Match) -> str | None:
    """Set the current match's current host by id."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp host <name>"

    target: Player | None = ctx.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target is match.host:
        return "They're already host, silly!"

    if target not in {slot.player for slot in match.slots}:
        return "Found no such player in the match."

    match.host_id = target.id

    match.host.enqueue(packets.match_transfer_host())
    match.enqueue_state(lobby=True)
    return "Match host updated."


@multiplayer_command(
    name="randpw",
    description="Randomize the current match's password.",
)
@ensure_match
async def mp_randpw(ctx: Context, match: Match) -> str | None:
    """Randomize the current match's password."""
    match.passwd = secrets.token_hex(8)
    return "Match password randomized."


@multiplayer_command(
    name="invite",
    triggers=["invite", "inv"],
    description="Invite a player to the current match by name.",
)
@ensure_match
async def mp_invite(ctx: Context, match: Match) -> str | None:
    """Invite a player to the current match by name."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp invite <name>"

    target = ctx.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target is ctx.state.sessions.bot:
        return "I'm too busy!"

    if target is ctx.player:
        return "You can't invite yourself!"

    target.enqueue(packets.match_invite(ctx.player, target.name))
    return f"Invited {target} to the match."


@multiplayer_command(
    name="addref",
    description="Add a referee to the current match by name.",
)
@ensure_match
async def mp_addref(ctx: Context, match: Match) -> str | None:
    """Add a referee to the current match by name."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp addref <name>"

    target: Player | None = ctx.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target not in {slot.player for slot in match.slots}:
        return "User must be in the current match!"

    if target in match.refs:
        return f"{target} is already a match referee!"

    match.referees.add(target)
    return f"{target.name} added to match referees."


@multiplayer_command(
    name="rmref",
    description="Remove a referee from the current match by name.",
)
@ensure_match
async def mp_rmref(ctx: Context, match: Match) -> str | None:
    """Remove a referee from the current match by name."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp rmref <name>"

    target = ctx.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target not in match.refs:
        return f"{target} is not a match referee!"

    if target is match.host:
        return "The host is always a referee!"

    match.referees.remove(target)
    return f"{target.name} removed from match referees."


@multiplayer_command(
    name="listref",
    description="List all referees from the current match.",
)
@ensure_match
async def mp_listref(ctx: Context, match: Match) -> str | None:
    """List all referees from the current match."""
    return ", ".join(map(str, match.refs)) + "."


@multiplayer_command(
    name="lock",
    description="Lock all unused slots in the current match.",
)
@ensure_match
async def mp_lock(ctx: Context, match: Match) -> str | None:
    """Lock all unused slots in the current match."""
    for slot in match.slots:
        if slot.status == SlotStatus.open:
            slot.status = SlotStatus.locked

    match.enqueue_state()
    return "All unused slots locked."


@multiplayer_command(
    name="unlock",
    description="Unlock locked slots in the current match.",
)
@ensure_match
async def mp_unlock(ctx: Context, match: Match) -> str | None:
    """Unlock locked slots in the current match."""
    for slot in match.slots:
        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open

    match.enqueue_state()
    return "All locked slots unlocked."


@multiplayer_command(
    name="teams",
    description="Change the team type for the current match.",
)
@ensure_match
async def mp_teams(ctx: Context, match: Match) -> str | None:
    """Change the team type for the current match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp teams <type>"

    team_type = ctx.args[0]

    if team_type in ("ffa", "freeforall", "head-to-head"):
        match.team_type = MatchTeamTypes.head_to_head
    elif team_type in ("tag", "coop", "co-op", "tag-coop"):
        match.team_type = MatchTeamTypes.tag_coop
    elif team_type in ("teams", "team-vs", "teams-vs"):
        match.team_type = MatchTeamTypes.team_vs
    elif team_type in ("tag-teams", "tag-team-vs", "tag-teams-vs"):
        match.team_type = MatchTeamTypes.tag_team_vs
    else:
        return "Unknown team type. (ffa, tag, teams, tag-teams)"

    # find the new appropriate default team.
    # defaults are (ffa: neutral, teams: red).
    if match.team_type in (MatchTeamTypes.head_to_head, MatchTeamTypes.tag_coop):
        new_t = MatchTeams.neutral
    else:
        new_t = MatchTeams.red

    # change each active slots team to
    # fit the correspoding team type.
    for s in match.slots:
        if s.player is not None:
            s.team = new_t

    if match.is_scrimming:
        # reset score if scrimming.
        match.reset_scrim()

    match.enqueue_state()
    return "Match team type updated."


@multiplayer_command(
    name="condition",
    triggers=["condition", "cond"],
    description="Change the win condition for the match.",
)
@ensure_match
async def mp_condition(ctx: Context, match: Match) -> str | None:
    """Change the win condition for the match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp condition <type>"

    cond = ctx.args[0]

    if cond == "pp":
        # special case - pp can't actually be used as an ingame
        # win condition, but bancho.py allows it to be passed into
        # this command during a scrims to use pp as a win cond.
        if not match.is_scrimming:
            return "PP is only useful as a win condition during scrims."
        if match.use_pp_scoring:
            return "PP scoring already enabled."

        match.use_pp_scoring = True
    else:
        if match.use_pp_scoring:
            match.use_pp_scoring = False

        if cond == "score":
            match.win_condition = MatchWinConditions.score
        elif cond in ("accuracy", "acc"):
            match.win_condition = MatchWinConditions.accuracy
        elif cond == "combo":
            match.win_condition = MatchWinConditions.combo
        elif cond in ("scorev2", "v2"):
            match.win_condition = MatchWinConditions.scorev2
        else:
            return "Invalid win condition. (score, acc, combo, scorev2, *pp)"

    match.enqueue_state(lobby=False)
    return "Match win condition updated."


@multiplayer_command(
    name="scrim",
    triggers=["scrim", "autoref"],
    description="Start a scrim in the current match.",
)
@ensure_match
async def mp_scrim(ctx: Context, match: Match) -> str | None:
    """Start a scrim in the current match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp scrim <bo#>"

    r_match = regexes.BEST_OF.fullmatch(ctx.args[0])
    if not r_match:
        return "Invalid syntax: !mp scrim <bo#>"

    best_of = int(r_match[1])
    if not 0 <= best_of < 16:
        return "Best of must be in range 0-15."

    winning_pts = (best_of // 2) + 1

    if winning_pts != 0:
        # setting to real num
        if match.is_scrimming:
            return "Already scrimming!"

        if best_of % 2 == 0:
            return "Best of must be an odd number!"

        match.is_scrimming = True
        msg = (
            f"A scrimmage has been started by {ctx.player.name}; "
            f"first to {winning_pts} points wins. Best of luck!"
        )
    else:
        # setting to 0
        if not match.is_scrimming:
            return "Not currently scrimming!"

        match.is_scrimming = False
        match.reset_scrim()
        msg = "Scrimming cancelled."

    match.winning_pts = winning_pts
    return msg


@multiplayer_command(
    name="endscrim",
    triggers=["endscrim", "end"],
    description="End the current matches ongoing scrim.",
)
@ensure_match
async def mp_endscrim(ctx: Context, match: Match) -> str | None:
    """End the current matches ongoing scrim."""
    if not match.is_scrimming:
        return "Not currently scrimming!"

    match.is_scrimming = False
    match.reset_scrim()
    return "Scrimmage ended."  # TODO: final score (get_score method?)


@multiplayer_command(
    name="rematch",
    triggers=["rematch", "rm"],
    description="Restart a scrim, or roll back previous match point.",
)
@ensure_match
async def mp_rematch(ctx: Context, match: Match) -> str | None:
    """Restart a scrim, or roll back previous match point."""
    if ctx.args:
        return "Invalid syntax: !mp rematch"

    if ctx.player is not match.host:
        return "Only available to the host."

    if not match.is_scrimming:
        if match.winning_pts == 0:
            msg = "No scrim to rematch; to start one, use !mp scrim."
        else:
            # re-start scrimming with old points
            match.is_scrimming = True
            msg = (
                f"A rematch has been started by {ctx.player.name}; "
                f"first to {match.winning_pts} points wins. Best of luck!"
            )
    else:
        # reset the last match point awarded
        if not match.winners:
            return "No match points have yet been awarded!"

        recent_winner = match.winners[-1]
        if recent_winner is None:
            return "The last point was a tie!"

        match.match_points[recent_winner] -= 1  # TODO: team name
        match.winners.pop()

        msg = f"A point has been deducted from {recent_winner}."

    return msg


@multiplayer_command(
    name="force",
    triggers=["force", "f"],
    description="Force a player into the current match by name.",
    privileges_level=Privileges.ADMINISTRATOR,
    hidden=True,
)
@ensure_match
async def mp_force(ctx: Context, match: Match) -> str | None:
    """Force a player into the current match by name."""
    # NOTE: this overrides any limits such as silences or passwd.
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp force <name>"

    target = ctx.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    target.join_match(match, match.passwd)
    return "Welcome."


@multiplayer_command(
    name="loadpool",
    triggers=["loadpool", "lp"],
    description="Load a mappool into the current match.",
)
@ensure_match
async def mp_loadpool(ctx: Context, match: Match) -> str | None:
    """Load a mappool into the current match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp loadpool <name>"

    if ctx.player is not match.host:
        return "Only available to the host."

    name = ctx.args[0]

    pool = await tourney_pools_repo.fetch_by_name(name)
    if pool is None:
        return "Could not find a pool by that name!"

    if match.tourney_pool is not None and match.tourney_pool["id"] == pool["id"]:
        return f"{pool['name']} already selected!"

    match.tourney_pool = pool
    return f"{pool['name']} selected."


@multiplayer_command(
    name="unloadpool",
    triggers=["unloadpool", "ulp"],
    description="Unload the current matches mappool.",
)
@ensure_match
async def mp_unloadpool(ctx: Context, match: Match) -> str | None:
    """Unload the current matches mappool."""
    if ctx.args:
        return "Invalid syntax: !mp unloadpool"

    if ctx.player is not match.host:
        return "Only available to the host."

    if not match.tourney_pool:
        return "No mappool currently selected!"

    match.tourney_pool = None
    return "Mappool unloaded."


@multiplayer_command(
    name="ban",
    description="Ban a pick in the currently loaded mappool.",
)
@ensure_match
async def mp_ban(ctx: Context, match: Match) -> str | None:
    """Ban a pick in the currently loaded mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp ban <pick>"

    if not match.tourney_pool:
        return "No pool currently selected!"

    mods_slot = ctx.args[0]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    map_pick = await tourney_pool_maps_repo.fetch_by_pool_and_pick(
        pool_id=match.tourney_pool["id"],
        mods=mods,
        slot=slot,
    )
    if map_pick is None:
        return f"Found no {mods_slot} pick in the pool."

    if (mods, slot) in match.bans:
        return "That pick is already banned!"

    match.bans.add((mods, slot))
    return f"{mods_slot} banned."


@multiplayer_command(
    name="unban",
    description="Unban a pick in the currently loaded mappool.",
)
@ensure_match
async def mp_unban(ctx: Context, match: Match) -> str | None:
    """Unban a pick in the currently loaded mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp unban <pick>"

    if not match.tourney_pool:
        return "No pool currently selected!"

    mods_slot = ctx.args[0]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    map_pick = await tourney_pool_maps_repo.fetch_by_pool_and_pick(
        pool_id=match.tourney_pool["id"],
        mods=mods,
        slot=slot,
    )
    if map_pick is None:
        return f"Found no {mods_slot} pick in the pool."

    if (mods, slot) not in match.bans:
        return "That pick is not currently banned!"

    match.bans.remove((mods, slot))
    return f"{mods_slot} unbanned."


@multiplayer_command(
    name="pick",
    description="Pick a map from the currently loaded mappool.",
)
@ensure_match
async def mp_pick(ctx: Context, match: Match) -> str | None:
    """Pick a map from the currently loaded mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp pick <pick>"

    if not match.tourney_pool:
        return "No pool currently loaded!"

    mods_slot = ctx.args[0]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    map_pick = await tourney_pool_maps_repo.fetch_by_pool_and_pick(
        pool_id=match.tourney_pool["id"],
        mods=mods,
        slot=slot,
    )
    if map_pick is None:
        return f"Found no {mods_slot} pick in the pool."

    if (mods, slot) in match.bans:
        return f"{mods_slot} has been banned from being picked."

    bmap = await Beatmap.from_bid(map_pick["map_id"])
    if not bmap:
        return f"Found no beatmap for {mods_slot} pick."

    match.map_md5 = bmap.md5
    match.map_id = bmap.id
    match.map_name = bmap.full_name

    # TODO: some kind of abstraction allowing
    # for something like !mp pick fm.
    if match.freemods:
        # if freemods are enabled, disable them.
        match.freemods = False

        for s in match.slots:
            if s.player is not None:
                s.mods = Mods.NOMOD

    # update match mods to the picked map.
    match.mods = mods

    match.enqueue_state()

    return f"Picked {bmap.embed}. ({mods_slot})"
