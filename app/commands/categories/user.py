"""
User Commands

Commands for user role.
"""

from __future__ import annotations

import random
import time
import uuid
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app import packets
from app import settings
from app.commands.base import CommandCategory
from app.commands.base import user_command
from app.commands.context import Context
from app.commands.help import generate_command_help
from app.commands.help import generate_help_message
from app.constants import regexes
from app.constants.gamemodes import GAMEMODE_REPR_LIST
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus
from app.objects.beatmap import ensure_osu_file_is_available
from app.objects.score import SubmissionStatus
from app.repositories import map_requests as map_requests_repo
from app.repositories import users as users_repo
from app.usecases.performance import ScoreParams
from app.usecases.performance import calculate_performances

# Define BEATMAPS_PATH
BEATMAPS_PATH = Path.cwd() / ".data/osu"


@user_command(
    name="help",
    triggers=["help", "h"],
    description="Show help for commands. Usage: !help [command|category]",
)
async def help_cmd(ctx: Context) -> str:
    """Show help for commands."""
    from app.commands import get_registry

    registry = get_registry()
    prefix = ctx.settings.COMMAND_PREFIX

    # No args - show general help
    if not ctx.args:
        return generate_help_message(registry, ctx.player)

    query = ctx.args[0].lower()

    # Check if query matches a category name
    for category in CommandCategory:
        if query == category.value.lower():
            return generate_help_message(registry, ctx.player, category=category)

    # Check if it's a namespaced command (e.g., "mp start")
    if len(ctx.args) >= 2:
        namespaced = registry.get_by_namespace(ctx.args[0].lower(), ctx.args[1].lower())
        if namespaced:
            return generate_command_help(
                registry, ctx.player, f"{ctx.args[0]} {ctx.args[1]}", prefix
            )

    # Check if it's a direct command trigger
    cmd = registry.get_by_trigger(query)
    if cmd:
        return generate_command_help(registry, ctx.player, query, prefix)

    # Check if it's a namespaced command trigger (e.g., "mp_help")
    namespaced_trigger = f"{query}_help"
    cmd = registry.get_by_trigger(namespaced_trigger)
    if cmd:
        return generate_command_help(registry, ctx.player, namespaced_trigger, prefix)

    # Search for partial matches
    return generate_help_message(registry, ctx.player, search_query=query)


@user_command(
    name="roll",
    description="Roll an n-sided die where n is the number you write (100 default).",
)
async def roll(ctx: Context) -> str:
    """Roll an n-sided die where n is the number you write (100 default)."""
    if ctx.args and ctx.args[0].isdecimal():
        max_roll = min(int(ctx.args[0]), 0x7FFF)
    else:
        max_roll = 100

    if max_roll == 0:
        return "Roll what?"

    points = random.randrange(0, max_roll)  # nosec B311
    return f"{ctx.player.name} rolls {points} points!"


@user_command(
    name="block",
    description="Block another user from communicating with you.",
    hidden=True,
)
async def block(ctx: Context) -> str:
    """Block another user from communicating with you."""
    target = await ctx.state.sessions.players.from_cache_or_sql(name=" ".join(ctx.args))

    if not target:
        return "User not found."

    if (
        ctx.state.sessions.bot and target is ctx.state.sessions.bot
    ) or target is ctx.player:
        return "What?"

    if target.id in ctx.player.blocks:
        return f"{target.name} already blocked!"

    if target.id in ctx.player.friends:
        ctx.player.friends.remove(target.id)

    await ctx.player.add_block(target)
    return f"Added {target.name} to blocked users."


@user_command(
    name="unblock",
    description="Unblock another user from communicating with you.",
    hidden=True,
)
async def unblock(ctx: Context) -> str:
    """Unblock another user from communicating with you."""
    target = await ctx.state.sessions.players.from_cache_or_sql(name=" ".join(ctx.args))

    if not target:
        return "User not found."

    if (
        ctx.state.sessions.bot and target is ctx.state.sessions.bot
    ) or target is ctx.player:
        return "What?"

    if target.id not in ctx.player.blocks:
        return f"{target.name} not blocked!"

    await ctx.player.remove_block(target)
    return f"Removed {target.name} from blocked users."


@user_command(
    name="reconnect",
    description="Disconnect and reconnect a given player (or self) to the server.",
)
async def reconnect(ctx: Context) -> str | None:
    """Disconnect and reconnect a given player (or self) to the server."""
    if ctx.args:
        # !reconnect <player>
        if not ctx.player.priv & Privileges.ADMINISTRATOR:
            return None  # requires admin

        target = ctx.state.sessions.players.get(name=" ".join(ctx.args))
        if not target:
            return "Player not found"
    else:
        # !reconnect
        target = ctx.player

    target.logout()

    return None


@user_command(
    name="changename",
    description="Change your username.",
)
async def changename(ctx: Context) -> str | None:
    """Change your username."""
    name = " ".join(ctx.args).strip()

    if not regexes.USERNAME.match(name):
        return "Must be 2-15 characters in length."

    if "_" in name and " " in name:
        return 'May contain "_" and " ", but not both.'

    if name in settings.DISALLOWED_NAMES:
        return "Disallowed username; pick another."

    if await users_repo.fetch_one(name=name):
        return "Username already taken by another player."

    # all checks passed, update their name
    await users_repo.partial_update(ctx.player.id, name=name)

    ctx.player.enqueue(
        packets.notification(f"Your username has been changed to {name}!"),
    )
    ctx.player.logout()

    return None


@user_command(
    name="maplink",
    triggers=["maplink", "bloodcat", "beatconnect", "chimu", "q"],
    description="Return a download link to the user's current map (situation dependant).",
)
async def maplink(ctx: Context) -> str:
    """Return a download link to the user's current map (situation dependant)."""
    bmap = None

    # priority: multiplayer -> spectator -> last np
    match = ctx.player.match
    spectating = ctx.player.spectating

    if match and match.map_id:
        bmap = await Beatmap.from_md5(match.map_md5)
    elif spectating and spectating.status.map_id:
        bmap = await Beatmap.from_md5(spectating.status.map_md5)
    elif ctx.player.last_np is not None and time.time() < ctx.player.last_np["timeout"]:
        bmap = ctx.player.last_np["bmap"]

    if bmap is None:
        return "No map found!"

    return f"[{settings.MIRROR_DOWNLOAD_ENDPOINT}/{bmap.set_id} {bmap.full_name}]"


@user_command(
    name="recent",
    triggers=["recent", "last", "r"],
    description="Show information about a player's most recent score.",
)
async def recent(ctx: Context) -> str:
    """Show information about a player's most recent score."""
    if ctx.args:
        target = ctx.state.sessions.players.get(name=" ".join(ctx.args))
        if not target:
            return "Player not found."
    else:
        target = ctx.player

    score = target.recent_score
    if not score:
        return "No scores found (only saves per play session)."

    if score.bmap is None:
        return "We don't have a beatmap on file for your recent score."

    score_lines = [f"[{score.mode!r}] {score.bmap.embed}", f"{score.acc:.2f}%"]

    if score.mods:
        score_lines.insert(1, f"+{score.mods!r}")

    score_lines = [" ".join(score_lines)]

    if score.passed:
        rank = score.rank if score.status == SubmissionStatus.BEST else "NA"
        score_lines.append(f"PASS {{{score.pp:.2f}pp #{rank}}}")
    # XXX: prior to v3.2.0, bancho.py didn't parse total_length from
    # the osu!api, and thus this can do some zerodivision moments.
    # this can probably be removed in the future, or better yet
    # replaced with a better system to fix the maps.
    elif score.bmap.total_length != 0:
        completion = score.time_elapsed / (score.bmap.total_length * 1000)
        score_lines.append(f"FAIL {{{completion * 100:.2f}% complete}})")
    else:
        score_lines.append("FAIL")

    return " | ".join(score_lines)


TOP_SCORE_FMTSTR = "{idx}. ({pp:.2f}pp) [https://osu.{domain}/b/{map_id} {artist} - {title} [{version}]]"


@user_command(
    name="top",
    description="Show information about a player's top 10 scores.",
    hidden=True,
)
async def top(ctx: Context) -> str:
    """Show information about a player's top 10 scores."""
    # !top <mode> (player)
    args_len = len(ctx.args)
    if args_len not in (1, 2):
        return "Invalid syntax: !top <mode> (player)"

    if ctx.args[0] not in GAMEMODE_REPR_LIST:
        return f"Valid gamemodes: {', '.join(GAMEMODE_REPR_LIST)}."

    if ctx.args[0] in (
        "rx!mania",
        "ap!taiko",
        "ap!catch",
        "ap!mania",
    ):
        return "Impossible gamemode combination."

    if args_len == 2:
        if not regexes.USERNAME.match(ctx.args[1]):
            return "Invalid username."

        # specific player provided
        user = await users_repo.fetch_one(name=ctx.args[1])
    else:
        # no player provided, use self
        user = await users_repo.fetch_one(id=ctx.player.id)

    if user is None:
        return "Player not found."

    # !top rx!std
    mode = GAMEMODE_REPR_LIST.index(ctx.args[0])

    scores = await ctx.state.services.database.fetch_all(
        "SELECT s.pp, b.artist, b.title, b.version, b.set_id map_set_id, b.id map_id "
        "FROM scores s "
        "LEFT JOIN maps b ON b.md5 = s.map_md5 "
        "WHERE s.userid = :user_id "
        "AND s.mode = :mode "
        "AND s.status = 2 "
        "AND b.status in (2, 3) "
        "ORDER BY s.pp DESC LIMIT 10",
        {"user_id": user["id"], "mode": mode},
    )
    if not scores:
        return "No scores"

    user_embed = f"[https://{settings.DOMAIN}/u/{user['id']} {user['name']}]"

    return "\n".join(
        [f"Top 10 scores for {user_embed} ({ctx.args[0]})."]
        + [
            TOP_SCORE_FMTSTR.format(idx=idx + 1, domain=settings.DOMAIN, **s)
            for idx, s in enumerate(scores)
        ],
    )


@user_command(
    name="_with",
    triggers=["with", "w"],
    description="Specify custom accuracy & mod combinations with `/np`.",
    hidden=True,
)
async def _with(ctx: Context) -> str:
    """Specify custom accuracy & mod combinations with `/np`."""
    if ctx.recipient is not ctx.state.sessions.bot:
        bot_name = ctx.state.sessions.bot.name if ctx.state.sessions.bot else "Bot"
        return f"This command can only be used in DM with {bot_name}."

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    bmap: Beatmap = ctx.player.last_np["bmap"]

    osu_file_available = await ensure_osu_file_is_available(
        bmap.id,
        expected_md5=bmap.md5,
    )
    if not osu_file_available:
        return "Mapfile could not be found; this incident has been reported."

    mode_vn = ctx.player.last_np["mode_vn"]

    command_args = parse__with__command_args(mode_vn, ctx.args)
    if isinstance(command_args, ParsingError):
        return str(command_args)

    msg_fields = []

    score_args = ScoreParams(mode=mode_vn)

    mods = command_args["mods"]
    if mods is not None:
        score_args.mods = mods
        msg_fields.append(f"{mods!r}")

    nmiss = command_args["nmiss"]
    if nmiss:
        score_args.nmiss = nmiss
        msg_fields.append(f"{nmiss}m")

    combo = command_args["combo"]
    if combo is not None:
        score_args.combo = combo
        msg_fields.append(f"{combo}x")

    acc = command_args["acc"]
    if acc is not None:
        score_args.acc = acc
        msg_fields.append(f"{acc:.2f}%")

    result = calculate_performances(
        osu_file_path=str(BEATMAPS_PATH / f"{bmap.id}.osu"),
        scores=[score_args],  # calculate one score
    )

    return "{msg}: {pp:.2f}pp ({stars:.2f}*)".format(
        msg=" ".join(msg_fields),
        pp=result[0]["performance"]["pp"],
        stars=result[0]["difficulty"]["stars"],  # (first score result)
    )


class ParsingError(str):
    """String subclass marking a command-argument parsing failure."""


def parse__with__command_args(
    mode: int,
    args: Sequence[str],
) -> Mapping[str, Any] | ParsingError:
    """Parse arguments for the !with command."""

    if not args or len(args) > 4:
        return ParsingError("Invalid syntax: !with <acc/nmiss/combo/mods ...>")

    # !with 95% 1m 429x hddt
    combo: int | None = None
    nmiss: int | None = None
    mods: Mods | None = None
    acc: float | None = None

    # parse acc, misses, combo and mods from arguments.
    # tried to balance complexity vs correctness here
    for arg in (str.lower(arg) for arg in args):
        # mandatory suffix, combo & nmiss
        if combo is None and arg.endswith("x") and arg[:-1].isdecimal():
            combo = int(arg[:-1])
            # if combo > bmap.max_combo:
            #    return "Invalid combo."
        elif nmiss is None and arg.endswith("m") and arg[:-1].isdecimal():
            nmiss = int(arg[:-1])
            # TODO: store nobjects?
            # if nmiss > bmap.combo:
            #    return "Invalid misscount."
        else:
            # optional prefix/suffix, mods & accuracy
            arg_stripped = arg.removeprefix("+").removesuffix("%")
            if mods is None and arg_stripped.isalpha() and len(arg_stripped) % 2 == 0:
                mods = Mods.from_modstr(arg_stripped)
                mods = mods.filter_invalid_combos(mode)
            elif acc is None and arg_stripped.replace(".", "", 1).isdecimal():
                acc = float(arg_stripped)
                if not 0 <= acc <= 100:
                    return ParsingError("Invalid accuracy.")
            else:
                return ParsingError(f"Unknown argument: {arg}")

    return {
        "acc": acc,
        "mods": mods,
        "combo": combo,
        "nmiss": nmiss,
    }


@user_command(
    name="request",
    triggers=["request", "req"],
    description="Request a beatmap for nomination.",
)
async def request(ctx: Context) -> str:
    """Request a beatmap for nomination."""
    if ctx.args:
        return "Invalid syntax: !request"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    bmap = ctx.player.last_np["bmap"]

    if bmap.status != RankedStatus.Pending and settings.REQUEST_PENDING_ONLY:
        return "Only pending maps may be requested for status change."

    map_requests = await map_requests_repo.fetch_all(
        map_id=bmap.id,
        player_id=ctx.player.id,
        active=True,
    )
    if map_requests:
        return "You already have an active nomination request for that map."

    await map_requests_repo.create(map_id=bmap.id, player_id=ctx.player.id, active=True)

    return "Request submitted."


@user_command(
    name="apikey",
    description="Generate a new api key & assign it to the player.",
)
async def apikey(ctx: Context) -> str:
    """Generate a new api key & assign it to the player."""
    if ctx.recipient is not ctx.state.sessions.bot:
        bot_name = ctx.state.sessions.bot.name if ctx.state.sessions.bot else "Bot"
        return f"Command only available in DMs with {bot_name}."

    # remove old token
    if ctx.player.api_key:
        ctx.state.sessions.api_keys.pop(ctx.player.api_key)

    # generate new token
    ctx.player.api_key = str(uuid.uuid4())

    await users_repo.partial_update(ctx.player.id, api_key=ctx.player.api_key)
    ctx.state.sessions.api_keys[ctx.player.api_key] = ctx.player.id

    return f"API key generated. Copy your api key from (this url)[http://{ctx.player.api_key}]."
