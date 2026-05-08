"""
Developer Commands

Commands for developer role.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import pprint
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import cpuinfo
import psutil
from pytimeparse.timeparse import timeparse

from app import settings
from app.commands.base import developer_command
from app.commands.context import Context
from app.constants.privileges import Privileges

if TYPE_CHECKING:
    pass


@developer_command(
    name="stealth",
    description="Toggle the developer's stealth, allowing them to be hidden.",
)
async def stealth(ctx: Context) -> str | None:
    """Toggle the developer's stealth, allowing them to be hidden."""
    ctx.player.stealth = not ctx.player.stealth
    return f"Stealth {'enabled' if ctx.player.stealth else 'disabled'}."


@developer_command(
    name="recalc",
    description="Recalculate pp for a given map, or all maps.",
)
async def recalc(ctx: Context) -> str | None:
    """Recalculate pp for a given map, or all maps."""
    return (
        "Please use tools/recalc.py instead.\n"
        f"If you need any support, join our Discord @ {settings.DISCORD_INVITE}"
    )


@developer_command(
    name="debug",
    description="Set the console's debug level.",
    hidden=True,
)
async def debug(ctx: Context) -> str | None:
    """Set the console's debug level."""
    if len(ctx.args) < 1:
        return "Invalid syntax: !debug <0-3>"
    settings.DEBUG_LEVEL = int(ctx.args[0])
    return f"Set Debug Level to {int(ctx.args[0])}."


@developer_command(
    name="debug_focus",
    description="Set the console's debug focus.",
    hidden=True,
)
async def debug_focus(ctx: Context) -> str | None:
    """Set the console's debug focus."""
    if len(ctx.args) < 1:
        return "Invalid syntax: !debugFocus <all/scores/leaderboards/messages/requests/client>"
    settings.DEBUG_FOCUS = ctx.args[0]  # ty: ignore[invalid-assignment]
    return f"Set Debug Focus to {ctx.args[0]}."


# NOTE: these commands will likely be removed
#       with the addition of a good frontend.
str_priv_dict = {
    "normal": Privileges.UNRESTRICTED,
    "verified": Privileges.VERIFIED,
    "whitelisted": Privileges.WHITELISTED,
    "supporter": Privileges.SUPPORTER,
    "premium": Privileges.PREMIUM,
    "alumni": Privileges.ALUMNI,
    "tournament": Privileges.TOURNEY_MANAGER,
    "nominator": Privileges.NOMINATOR,
    "mod": Privileges.MODERATOR,
    "admin": Privileges.ADMINISTRATOR,
    "developer": Privileges.DEVELOPER,
}


@developer_command(
    name="addpriv",
    description="Set privileges for a specified player (by name).",
    hidden=True,
)
async def addpriv(ctx: Context) -> str | None:
    """Set privileges for a specified player (by name)."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !addpriv <name> <role1 role2 role3 ...>"

    bits = Privileges(0)

    for m in [m.lower() for m in ctx.args[1:]]:
        if m not in str_priv_dict:
            return f"Not found: {m}."

        bits |= str_priv_dict[m]

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return "Could not find user."

    if bits & Privileges.DONATOR != 0:
        return "Please use the !givedonator command to assign donator privileges to players."

    await target.add_privs(bits)
    return f"Updated {target}'s privileges."


@developer_command(
    name="rmpriv",
    description="Set privileges for a specified player (by name).",
    hidden=True,
)
async def rmpriv(ctx: Context) -> str | None:
    """Set privileges for a specified player (by name)."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !rmpriv <name> <role1 role2 role3 ...>"

    bits = Privileges(0)

    for m in [m.lower() for m in ctx.args[1:]]:
        if m not in str_priv_dict:
            return f"Not found: {m}."

        bits |= str_priv_dict[m]

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return "Could not find user."

    await target.remove_privs(bits)

    if bits & Privileges.DONATOR != 0:
        target.donor_end = 0
        await ctx.state.services.database.execute(
            "UPDATE users SET donor_end = 0 WHERE id = :user_id",
            {"user_id": target.id},
        )

    return f"Updated {target}'s privileges."


@developer_command(
    name="givedonator",
    description="Give donator status to a specified player for a specified duration.",
    hidden=True,
)
async def givedonator(ctx: Context) -> str | None:
    """Give donator status to a specified player for a specified duration."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !givedonator <name> <duration>"

    target = await ctx.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return "Could not find user."

    timespan = timeparse(ctx.args[1])
    if not timespan:
        return "Invalid timespan."

    if target.donor_end < time.time():
        timespan += time.time()
    else:
        timespan += target.donor_end

    target.donor_end = int(timespan)
    await ctx.state.services.database.execute(
        "UPDATE users SET donor_end = :end WHERE id = :user_id",
        {"end": timespan, "user_id": target.id},
    )

    await target.add_privs(Privileges.SUPPORTER)

    return f"Added {ctx.args[1]} of donator status to {target}."


@developer_command(
    name="wipemap",
    description="Wipe scores for a map.",
)
async def wipemap(ctx: Context) -> str | None:
    # (intentionally no docstring)
    if ctx.args:
        return "Invalid syntax: !wipemap"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    map_md5 = ctx.player.last_np["bmap"].md5

    # delete scores from all tables
    await ctx.state.services.database.execute(
        "DELETE FROM scores WHERE map_md5 = :map_md5",
        {"map_md5": map_md5},
    )

    return "Scores wiped."


@developer_command(
    name="reload",
    triggers=["reload", "re"],
    description="Reload a python module.",
)
async def reload(ctx: Context) -> str | None:
    """Reload a python module."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !reload <module>"

    parent, *children = ctx.args[0].split(".")

    try:
        mod = __import__(parent)
    except ModuleNotFoundError:
        return "Module not found."

    child = None
    try:
        for child in children:
            mod = getattr(mod, child)
    except AttributeError:
        return f"Failed at {child}."

    try:
        mod = importlib.reload(mod)
    except TypeError as exc:
        return f"{exc.args[0]}."

    return f"Reloaded {mod.__name__}"


@developer_command(
    name="server",
    description="Retrieve performance data about the server.",
)
async def server(ctx: Context) -> str | None:
    """Retrieve performance data about the server."""
    build_str = f"bancho.py v{settings.VERSION} ({settings.DOMAIN})"

    # get info about this process
    proc = psutil.Process(os.getpid())
    uptime = int(time.time() - proc.create_time())

    # get info about our cpu
    cpu_info = cpuinfo.get_cpu_info()

    # list of all cpus installed with thread count
    thread_count = cpu_info["count"]
    cpu_name = cpu_info["brand_raw"]

    cpu_info_str = f"{thread_count}x {cpu_name}"

    # get system-wide ram usage
    sys_ram = psutil.virtual_memory()

    # output ram usage as `{bancho_used}MB / {sys_used}MB / {sys_total}MB`
    bancho_ram = proc.memory_info()[0]
    ram_values = (bancho_ram, sys_ram.used, sys_ram.total)
    ram_info = " / ".join([f"{v // 1024**2}MB" for v in ram_values])

    # current state of settings
    mirror_search_url = urlparse(settings.MIRROR_SEARCH_ENDPOINT).netloc
    mirror_download_url = urlparse(settings.MIRROR_DOWNLOAD_ENDPOINT).netloc
    using_osuapi = bool(settings.OSU_API_KEY)
    advanced_mode = settings.DEVELOPER_MODE
    auto_logging = settings.AUTOMATICALLY_REPORT_PROBLEMS

    # package versioning info
    # divide up pkg versions, 3 displayed per line, e.g.
    # aiohttp v3.6.3 | aiomysql v0.0.21 | bcrypt v3.2.0
    # cmyui v1.7.3 | datadog v0.40.1 | geoip2 v4.1.0
    # maniera v1.0.0 | mysql-connector-python v8.0.23 | orjson v3.5.1
    # psutil v5.8.0 | py3rijndael v0.3.3 | uvloop v0.15.2
    requirements = []

    for dist in importlib.metadata.distributions():
        requirements.append(f"{dist.name} v{dist.version}")
    requirements.sort(key=lambda x: x.casefold())

    requirements_info = "\n".join(
        " | ".join(section)
        for section in (requirements[i : i + 3] for i in range(0, len(requirements), 3))
    )

    return "\n".join(
        (
            f"{build_str} | uptime: {timedelta(seconds=uptime)}",
            f"cpu: {cpu_info_str}",
            f"ram: {ram_info}",
            f"search mirror: {mirror_search_url} | download mirror: {mirror_download_url}",
            f"osu!api connection: {using_osuapi}",
            f"advanced mode: {advanced_mode} | auto logging: {auto_logging}",
            "",
            "requirements",
            requirements_info,
        ),
    )


if settings.DEVELOPER_MODE:
    """Advanced (& potentially dangerous) commands"""

    # NOTE: some of these commands are potentially dangerous, and only
    # really intended for advanced users looking for access to lower level
    # utilities. Some may give direct access to utilties that could perform
    # harmful tasks to the underlying machine, so use at your own risk.

    from sys import modules as installed_mods

    __py_namespace: dict[str, Any] = globals() | {
        mod: importlib.import_module(mod)
        for mod in (
            "asyncio",
            "dis",
            "os",
            "sys",
            "struct",
            "discord",
            "datetime",
            "time",
            "inspect",
            "math",
            "importlib",
        )
        if mod in installed_mods
    }

    @developer_command(
        name="py",
        description="Allow for (async) access to the python interpreter.",
    )
    async def py(ctx: Context) -> str | None:
        """Allow for (async) access to the python interpreter."""
        # This can be very good for getting used to bancho.py's API; just look
        # around the codebase and find things to play with in your server.
        # Ex: !py return (await app.state.sessions.players.get(name='cmyui')).status.action
        if not ctx.args:
            return "owo"

        # turn our input args into a coroutine definition string.
        definition = "\n ".join(["async def __py(ctx):", " ".join(ctx.args)])

        try:  # def __py(ctx)
            exec(
                definition, __py_namespace
            )  # noqa: S102  # nosec B102  # add to namespace
            ret = await __py_namespace["__py"](ctx)  # await it's return
        except Exception as exc:  # return exception in osu! chat
            ret = f"{exc.__class__}: {exc}"

        if "__py" in __py_namespace:
            del __py_namespace["__py"]

        if not isinstance(ret, str):
            ret = pprint.pformat(ret, compact=True)

        return str(ret)
