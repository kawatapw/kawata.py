""" cho: handle cho packets from the osu! client """

from __future__ import annotations

import time
import random
from app.constants.aeris_features import AerisFeatures
from fastapi import Response
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi import Response
from fastapi.param_functions import Header
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

import app.packets
import app.settings
import app.state
import app.usecases.performance
import app.utils
from app.logging import Ansi
from app.logging import log
from app.objects.player import Player
from app.packets import BanchoPacketReader
from .packets import aeris, osu, common

from app import commands
from app._typing import IPAddress
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.logging import magnitude_fmt_time
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_local_osu_file
from app.objects.channel import Channel
from app.objects.clan import Clan
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import MatchWinConditions
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.player import Action
from app.objects.player import ClientDetails
from app.objects.player import OsuStream
from app.objects.player import OsuVersion
from app.objects.player import Player
from app.objects.player import PresenceFilter
from app.packets import BanchoPacketReader
from app.packets import BasePacket
from app.packets import ClientPackets
from app.repositories import ingame_logins as logins_repo
from app.repositories import players as players_repo
from app.state import services
from app.usecases.performance import ScoreParams
from app.api.domains.packets.common import register

OSU_API_V2_CHANGELOG_URL = "https://osu.ppy.sh/api/v2/changelog"

BEATMAPS_PATH = Path.cwd() / ".data/osu"

BASE_DOMAIN = app.settings.DOMAIN

AERIS_IDENTIFICATION = AerisFeatures.Groups
if (app.settings.CHEAT_SERVER):
    AERIS_IDENTIFICATION |= AerisFeatures.Cheats

router = APIRouter(tags=["Bancho API"])


@router.get("/")
async def bancho_http_handler() -> Response:
    """Handle a request from a web browser."""
    new_line = "\n"
    matches = [m for m in app.state.sessions.matches if m is not None]
    players = [p for p in app.state.sessions.players if not p.is_bot_client]

    packets = app.state.packets["all"]

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<body style="font-family: monospace; white-space: pre-wrap;">Running bancho.py v{app.settings.VERSION}

<a href="online">{len(players)} online players</a>
<a href="matches">{len(matches)} matches</a>

<b>packets handled ({len(packets)})</b>
{new_line.join([f"{packet.name} ({packet.value})" for packet in packets])}

<a href="https://github.com/kawatapw/kawata.py">Source code</a>
</body>
</html>""",
    )

@router.get("/infos")
async def bancho_view_infos() -> Response:
    """Get server information"""
    data = {
        "version": AERIS_IDENTIFICATION,
        "latestClientVersion": "20240206.2",
        "motd": "osu!Kawata Welcome! | " + random.choice(common.motds),
        "onlineUsers": len([player for player in app.state.sessions.players if not player.bot_client]),
        "icon": "https://kawata.pw/static/images/logo.png"
    }

    return JSONResponse(data)


@router.get("/online")
async def bancho_view_online_users() -> Response:
    """see who's online"""
    new_line = "\n"

    players: list[Player] = []
    bots: list[Player] = []
    for p in app.state.sessions.players:
        if p.is_bot_client:
            bots.append(p)
        else:
            players.append(p)

    id_max_length = len(str(max(p.id for p in app.state.sessions.players)))

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<body style="font-family: monospace;  white-space: pre-wrap;"><a href="/">back</a>
users:
{new_line.join([f"({p.id:>{id_max_length}}): {p.safe_name}" for p in players])}
bots:
{new_line.join(f"({p.id:>{id_max_length}}): {p.safe_name}" for p in bots)}
</body>
</html>""",
    )


@router.get("/matches")
async def bancho_view_matches() -> Response:
    """ongoing matches"""
    new_line = "\n"

    ON_GOING = "ongoing"
    IDLE = "idle"
    max_status_length = len(max(ON_GOING, IDLE))

    BEATMAP = "beatmap"
    HOST = "host"
    max_properties_length = max(len(BEATMAP), len(HOST))

    matches = [m for m in app.state.sessions.matches if m is not None]

    match_id_max_length = (
        len(str(max(match.id for match in matches))) if len(matches) else 0
    )

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<body style="font-family: monospace;  white-space: pre-wrap;"><a href="/">back</a>
matches:
{new_line.join(
    f'''{(ON_GOING if m.in_progress else IDLE):<{max_status_length}} ({m.id:>{match_id_max_length}}): {m.name}
-- '''
    + f"{new_line}-- ".join([
        f'{BEATMAP:<{max_properties_length}}: {m.map_name}',
        f'{HOST:<{max_properties_length}}: <{m.host.id}> {m.host.safe_name}'
    ]) for m in matches
)}
</body>
</html>""",
    )


@router.post("/")
async def bancho_handler(
    request: Request,
    osu_token: str | None = Header(None),
    user_agent: Literal["osu!"] = Header(...),
) -> Response:
    ip = app.state.services.ip_resolver.get_ip(request.headers)

    if osu_token is None:
        # the client is performing a login
        async with app.state.services.database.connection() as db_conn:
            request._body = await request.body()
            log(f"Login request from {ip}.\nRequest Body: {request._body}", Ansi.LCYAN, file=".data/logs/login.log")
            login_data = await osu.handle_osu_login_request(
                request.headers,
                request._body,
                ip,
                db_conn,
            )

        return Response(
            content=login_data["response_body"],
            headers={"cho-token": login_data["osu_token"]},
        )

    # get the player from the specified osu token.
    player = app.state.sessions.players.get(token=osu_token)

    if not player:
        # chances are, we just restarted the server
        # tell their client to reconnect immediately.
        return Response(
            content=(
                app.packets.notification("Server has restarted.")
                + app.packets.restart_server(0)  # ms until reconnection
            ),
        )

    if player.restricted:
        # restricted users may only use certain packet handlers.
        packet_map = app.state.packets["restricted"]
    else:
        packet_map = app.state.packets["all"]

    # bancho connections can be comprised of multiple packets;
    # our reader is designed to iterate through them individually,
    # allowing logic to be implemented around the actual handler.
    # NOTE: any unhandled packets will be ignored internally.

    with memoryview(await request.body()) as body_view:
        if app.settings.DEBUG and app.settings.DEBUG_REQUESTS:
            log(f"Packet from {player}: {body_view}", Ansi.GRAY, file=".data/logs/packets.log")
        for packet in BanchoPacketReader(body_view, packet_map):
            await packet.handle(player)

    player.last_recv_time = time.time()

    response_data = player.dequeue()
    return Response(content=response_data)
