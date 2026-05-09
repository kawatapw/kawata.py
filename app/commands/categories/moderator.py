"""
Moderator Commands

Commands for moderator role.
"""

from __future__ import annotations

from pytimeparse.timeparse import timeparse

from app.commands.base import moderator_command
from app.commands.context import Context
from app.constants.privileges import Privileges
from app.repositories import logs as logs_repo

# Define ACTION_STRINGS for mapping action types to display strings
ACTION_STRINGS = {
    "restrict": "Restricted for",
    "unrestrict": "Unrestricted for",
    "silence": "Silenced for",
    "unsilence": "Unsilenced for",
    "note": "Note added:",
}


@moderator_command(
    name="notes",
    description="Retrieve the logs of a specified player by name.",
    hidden=True,
)
async def notes(ctx: Context) -> str:
    """Retrieve the logs of a specified player by name."""
    if len(ctx.args) != 2 or not ctx.args[1].isdecimal():
        return "Invalid syntax: !notes <name> <days_back>"

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    days = int(ctx.args[1])

    if days > 365:
        return "Please contact a developer to fetch >365 day old information."
    if days <= 0:
        return "Invalid syntax: !notes <name> <days_back>"

    res = await ctx.state.services.database.fetch_all(
        "SELECT `action`, `reason`, `time`, `mod` "
        "FROM `logs` WHERE `target` = :target "
        "AND UNIX_TIMESTAMP(`time`) >= UNIX_TIMESTAMP(NOW()) - :seconds "
        "ORDER BY `time` ASC",
        {"target": target.id, "seconds": days * 86400},
    )

    if not res:
        return f"No notes found on {target} in the past {days} days."

    notes = []
    for row in res:
        logger = await ctx.state.sessions.players.from_cache_or_sql(id=row["mod"])
        if not logger:
            continue

        action_str = ACTION_STRINGS.get(row["action"], "Unknown action:")
        time_str = row["time"]
        note = row["reason"]

        notes.append(f"[{time_str}] {action_str} {note} by {logger.name}")

    return "\n".join(notes)


@moderator_command(
    name="addnote",
    description="Add a note to a specified player by name.",
    hidden=True,
)
async def addnote(ctx: Context) -> str:
    """Add a note to a specified player by name."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !addnote <name> <note ...>"

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    await logs_repo.create(
        from_id=ctx.player.id,
        to_id=target.id,
        action="note",
        msg=" ".join(ctx.args[1:]),
        action_type=3,
    )

    return f"Added note to {target}."


# some shorthands that can be used as
# reasons in many moderative commands.
SHORTHAND_REASONS = {
    "aa": "having their appeal accepted",
    "cc": "using a modified osu! client",
    "3p": "using 3rd party programs",
    "rx": "using 3rd party programs (relax)",
    "tw": "using 3rd party programs (timewarp)",
    "au": "using 3rd party programs (auto play)",
}


@moderator_command(
    name="silence",
    description="Silence a specified player with a specified duration & reason.",
    hidden=True,
)
async def silence(ctx: Context) -> str:
    """Silence a specified player with a specified duration & reason."""
    if len(ctx.args) < 3:
        return "Invalid syntax: !silence <name> <duration> <reason>"

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    duration = timeparse(ctx.args[1])
    if not duration:
        return "Invalid timespan."

    reason = " ".join(ctx.args[2:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await target.silence(ctx.player, duration, reason)
    return f"{target} was silenced."


@moderator_command(
    name="unsilence",
    description="Unsilence a specified player.",
    hidden=True,
)
async def unsilence(ctx: Context) -> str:
    """Unsilence a specified player."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !unsilence <name> <reason>"

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if not target.silenced:
        return f"{target} is not silenced."

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    reason = " ".join(ctx.args[1:])

    await target.unsilence(ctx.player, reason)
    return f"{target} was unsilenced."
