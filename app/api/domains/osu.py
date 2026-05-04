"""
OSU Domain Module - osu! Web API and Score Submission Handler

This module implements the core osu! web API endpoints and score submission
handling for the osu! server application. It provides comprehensive functionality
for beatmap information retrieval, score submission processing, leaderboard
management, user registration, and various other osu! client interactions.

The module serves as the primary interface between the osu! client and the
server's game logic, handling all web-based API requests including score
submissions, beatmap information queries, user authentication, and various
utility endpoints required for full osu! client compatibility.

Key Features:
    - Score submission processing with anti-cheat validation
    - Beatmap information retrieval and caching
    - Leaderboard generation with multiple filtering options
    - User registration and account management
    - Replay file handling and storage
    - Achievement system integration
    - Comment and rating systems
    - Screenshot upload and management
    - osu!direct search functionality
    - Client update checking and redirection

Integration Points:
    - Score processing in app/objects/score.py
    - Beatmap management in app/objects/beatmap.py
    - Player management in app/objects/player.py
    - Achievement system in app/usecases/achievements.py
    - Database operations in app/repositories/
    - Anti-cheat validation in app/constants/clientflags.py
    - Performance calculation in app/usecases/performance.py

API Endpoints:
    - POST /web/osu-submit-modular.php: Score submission (legacy)
    - POST /web/osu-submit-modular-selector.php: Score submission (modern)
    - GET /web/osu-getbeatmapinfo.php: Beatmap information
    - GET /web/osu-search.php: osu!direct search
    - GET /web/osu-search-set.php: Beatmap set search
    - GET /web/osu-getreplay.php: Replay file retrieval
    - GET /web/osu-getfriends.php: Friends list
    - GET /web/osu-getfavourites.php: Favourites list
    - GET /web/osu-addfavourite.php: Add favourite
    - POST /web/osu-comment.php: Comment system
    - GET /web/osu-rate.php: Beatmap rating
    - POST /users: User registration
    - GET /ss/{id}.{ext}: Screenshot retrieval
    - GET /d/{set_id}: Beatmap download

Score Submission Flow:
    1. Client submits score data with replay file
    2. Server validates authentication and session
    3. Score data is decrypted and parsed
    4. Anti-cheat checks are performed
    5. Beatmap and player data are retrieved
    6. Score is validated and processed
    7. Performance points are calculated
    8. Achievements are checked and awarded
    9. Statistics are updated
    10. Response charts are generated and sent

Security Features:
    - Session token validation
    - Score checksum verification
    - Anti-cheat flag processing
    - Hardware hash validation
    - Rate limiting on submissions
    - Input validation and sanitization

Usage Pattern:
    # Score submission endpoint
    POST /web/osu-submit-modular-selector.php
    Headers: osu-token, User-Agent
    Body: multipart form with score data and replay

    # Beatmap information
    GET /web/osu-getbeatmapinfo.php?u=username&h=pass&f[]=filename

    # Leaderboard retrieval
    GET /web/osu-osz2-getscores.php?us=username&ha=pass&c=map_md5

Related Files:
    - app/objects/score.py: Score data model and processing
    - app/objects/beatmap.py: Beatmap data and caching
    - app/objects/player.py: Player session management
    - app/usecases/achievements.py: Achievement validation
    - app/repositories/scores.py: Score database operations
    - app/usecases/performance.py: Performance calculation
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import random
import secrets
import shutil
import time
import zipfile
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from enum import IntEnum, unique
from functools import cache
from pathlib import Path as SystemPath
from typing import Annotated, Any, Literal, cast
from urllib.parse import unquote, unquote_plus

import bcrypt
from fastapi import status
from fastapi.datastructures import FormData, UploadFile
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends, File, Form, Header, Path, Query
from fastapi.requests import Request
from fastapi.responses import FileResponse, ORJSONResponse, RedirectResponse, Response
from fastapi.routing import APIRouter
from starlette.datastructures import UploadFile as StarletteUploadFile

import app.packets
import app.settings
import app.state
import app.utils
from app import encryption
from app._typing import UNSET
from app.constants import regexes
from app.constants.clientflags import LastFMFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.logging import Ansi, error_catcher, log, logLevel
from app.objects import models
from app.objects.beatmap import Beatmap, RankedStatus, ensure_osu_file_is_available
from app.objects.player import ModeData, Player
from app.objects.score import Grade, Score, SubmissionStatus
from app.repositories import clans as clans_repo
from app.repositories import comments as comments_repo
from app.repositories import favourites as favourites_repo
from app.repositories import mail as mail_repo
from app.repositories import maps as maps_repo
from app.repositories import ratings as ratings_repo
from app.repositories import scores as scores_repo
from app.repositories import seasons as seasons_repo
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo
from app.repositories.achievements import Achievement
from app.usecases import achievements as achievements_usecases
from app.usecases import user_achievements as user_achievements_usecases
from app.utils import escape_enum, pymysql_encode

BEATMAPS_PATH = SystemPath.cwd() / ".data/osu"
REPLAYS_PATH = SystemPath.cwd() / ".data/osr"
SCREENSHOTS_PATH = SystemPath.cwd() / ".data/ss"


router = APIRouter(
    tags=["osu! web API"],
    default_response_class=Response,
)


@cache
def authenticate_player_session(
    param_function: Callable[..., Any],
    username_alias: str = "u",
    pw_md5_alias: str = "p",
    err: Any | None = None,
) -> Callable[[str, str], Awaitable[Player]]:
    async def wrapper(
        username: str = param_function(..., alias=username_alias),
        pw_md5: str = param_function(..., alias=pw_md5_alias),
    ) -> Player:
        player: Player | None = await app.state.sessions.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
        if player:
            return player

        # player login incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err,
        )

    return wrapper


""" /web/ handlers """

# Unhandled endpoints:
# POST /web/osu-error.php
# POST /web/osu-session.php
# POST /web/osu-osz2-bmsubmit-post.php
# POST /web/osu-osz2-bmsubmit-upload.php
# GET /web/osu-osz2-bmsubmit-getid.php
# GET /web/osu-get-beatmap-topic.php


authenticate_screenshot = authenticate_player_session(Form, "u", "p")


@router.post("/web/osu-screenshot.php")
@error_catcher
async def osuScreenshot(
    player: Player = Depends(authenticate_screenshot),  # noqa: B008
    endpoint_version: int = Form(..., alias="v"),  # noqa: B008
    screenshot_file: UploadFile = File(..., alias="ss"),  # noqa: B008
) -> Response:
    with memoryview(await screenshot_file.read()) as screenshot_view:
        # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
        if len(screenshot_view) > (4 * 1024 * 1024):
            return Response(
                content=b"Screenshot file too large.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if endpoint_version != 1:
            await app.state.services.log_strange_occurrence(
                f"Incorrect endpoint version (/web/osu-screenshot.php v{endpoint_version})",
            )

        if app.utils.has_jpeg_headers_and_trailers(screenshot_view):
            extension = "jpeg"
        elif app.utils.has_png_headers_and_trailers(screenshot_view):
            extension = "png"
        else:
            return Response(
                content=b"Invalid file type",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        while True:
            filename = f"{secrets.token_urlsafe(6)}.{extension}"
            ss_file = SCREENSHOTS_PATH / filename
            if not ss_file.exists():
                break

        with ss_file.open("wb") as f:
            f.write(screenshot_view)

    log(f"{player} uploaded {filename}.")
    return Response(filename.encode())


authenticate_friends = authenticate_player_session(Query, "u", "h")


@router.get("/web/osu-getfriends.php")
@error_catcher
async def osuGetFriends(
    player: Player = Depends(authenticate_friends),  # noqa: B008
) -> Response:
    return Response("\n".join(map(str, player.friends)).encode())


def bancho_to_osuapi_status(bancho_status: int) -> int:
    return {
        0: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4,
    }[bancho_status]


@router.post("/web/osu-getbeatmapinfo.php")
async def osuGetBeatmapInfo(
    form_data: models.OsuBeatmapRequestForm,
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
) -> Response:
    num_requests = len(form_data.Filenames) + len(form_data.Ids)
    log(f"{player} requested info for {num_requests} maps.", Ansi.LCYAN)

    response_lines: list[str] = []

    for idx, map_filename in enumerate(form_data.Filenames):
        # try getting the map from sql

        beatmap = await maps_repo.fetch_one(filename=map_filename)

        if not beatmap:
            continue

        # try to get the user's grades on the map
        # NOTE: osu! only allows us to send back one per gamemode,
        #       so we've decided to send back *vanilla* grades.
        #       (in theory we could make this user-customizable)
        grades = ["N", "N", "N", "N"]

        for score in await scores_repo.fetch_many(
            map_md5=beatmap["md5"],
            user_id=player.id,
            mode=player.status.mode.as_vanilla,
            status=SubmissionStatus.BEST,
        ):
            grades[score["mode"]] = score["grade"]

        response_lines.append(
            "{i}|{id}|{set_id}|{md5}|{status}|{grades}".format(
                i=idx,
                id=beatmap["id"],
                set_id=beatmap["set_id"],
                md5=beatmap["md5"],
                status=bancho_to_osuapi_status(beatmap["status"]),
                grades="|".join(grades),
            ),
        )

    if form_data.Ids:  # still have yet to see this used
        await app.state.services.log_strange_occurrence(
            f"{player} requested map(s) info by id ({form_data.Ids})",
        )

    return Response("\n".join(response_lines).encode())


@router.get("/web/osu-getfavourites.php")
@error_catcher
async def osuGetFavourites(
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
) -> Response:
    favourites = await favourites_repo.fetch_all(userid=player.id)

    return Response(
        "\n".join([str(favourite["setid"]) for favourite in favourites]).encode(),
    )


@router.get("/web/osu-addfavourite.php")
@error_catcher
async def osuAddFavourite(
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
    map_set_id: Annotated[int, Query(..., alias="a")],
) -> Response:
    # check if they already have this favourited.
    if await favourites_repo.fetch_one(player.id, map_set_id):
        return Response(b"You've already favourited this beatmap!")

    # add favourite
    await favourites_repo.create(
        userid=player.id,
        setid=map_set_id,
    )

    return Response(b"Added favourite!")


@router.get("/web/lastfm.php")
@error_catcher
async def lastFM(
    action: Literal["scrobble", "np"],
    beatmap_id_or_hidden_flag: Annotated[
        str,
        Query(
            ...,
            description=(
                "This flag is normally a beatmap ID, but is also "
                "used as a hidden anticheat flag within osu!"
            ),
            alias="b",
        ),
    ],
    player: Annotated[Player, Depends(authenticate_player_session(Query, "us", "ha"))],
) -> Response:
    if beatmap_id_or_hidden_flag[0] != "a":
        # not anticheat related, tell the
        # client not to send any more for now.
        return Response(b"-3")

    if not app.settings.CHEAT_SERVER:
        flags = LastFMFlags(int(beatmap_id_or_hidden_flag[1:]))

        if flags & (LastFMFlags.HQ_ASSEMBLY | LastFMFlags.HQ_FILE):
            # Player is currently running hq!osu; could possibly
            # be a separate client, buuuut prooobably not lol.

            await player.restrict(
                admin=app.state.sessions.bot,
                reason=f"hq!osu running ({flags})",
            )

            # refresh their client state
            if player.is_online:
                player.logout()

            return Response(b"-3")

        if flags & LastFMFlags.REGISTRY_EDITS:
            # Player has registry edits left from
            # hq!osu's multiaccounting tool. This
            # does not necessarily mean they are
            # using it now, but they have in the past.

            if random.randrange(32) == 0:  # nosec B311
                # Random chance (1/32) for a ban.
                await player.restrict(
                    admin=app.state.sessions.bot,
                    reason="hq!osu relife 1/32",
                )

                # refresh their client state
                if player.is_online:
                    player.logout()

                return Response(b"-3")

            player.enqueue(
                app.packets.notification(
                    "\n".join(
                        [
                            "Hey!",
                            "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
                            "This tool leaves a change in your registry that the osu! client can detect.",
                            "Please re-install relife and disable the program to avoid any restrictions.",
                        ],
                    ),
                ),
            )

            player.logout()

            return Response(b"-3")

        """ These checks only worked for ~5 hours from release. rumoi's quick!
        if flags & (
            LastFMFlags.SDL2_LIBRARY
            | LastFMFlags.OPENSSL_LIBRARY
            | LastFMFlags.AQN_MENU_SAMPLE
        ):
            # AQN has been detected in the client, either
            # through the 'libeay32.dll' library being found
            # onboard, or from the menu sound being played in
            # the AQN menu while being in an inappropriate menu
            # for the context of the sound effect.
            pass
        """

    return Response(b"")


DIRECT_SET_INFO_FMTSTR = (
    "{SetID}.osz|{Artist}|{Title}|{Creator}|"
    "{RankedStatus}|10.0|{LastUpdate}|{SetID}|"
    "0|{HasVideo}|0|0|0|{diffs}"  # 0s are threadid, has_story,
    # filesize, filesize_novid.
)

DIRECT_MAP_INFO_FMTSTR = (
    "[{DifficultyRating:.2f}⭐] {DiffName} "
    "{{cs: {CS} / od: {OD} / ar: {AR} / hp: {HP}}}@{Mode}"
)


@router.get("/web/osu-search.php")
@error_catcher
async def osuSearchHandler(
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
    ranked_status: Annotated[int, Query(..., alias="r", ge=0, le=8)],
    query: Annotated[str, Query(..., alias="q")],
    mode: Annotated[int, Query(..., alias="m", ge=-1, le=3)],  # -1 for all
    page_num: Annotated[int, Query(..., alias="p")],
) -> Response:
    params: dict[str, Any] = {"amount": 100, "offset": page_num * 100}

    # eventually we could try supporting these,
    # but it mostly depends on the mirror.
    if query not in ("Newest", "Top+Rated", "Most+Played"):
        params["query"] = query

    if mode != -1:  # -1 for all
        params["mode"] = mode

    if ranked_status != 4:  # 4 for all
        # convert to osu!api status
        params["status"] = RankedStatus.from_osudirect(ranked_status).osu_api

    response = await app.state.services.http_client.get(
        app.settings.MIRROR_SEARCH_ENDPOINT,
        params=params,
    )
    if response.status_code != status.HTTP_200_OK:
        return Response(b"-1\nFailed to retrieve data from the beatmap mirror.")

    result = response.json()

    lresult = len(result)  # send over 100 if we receive
    # 100 matches, so the client
    # knows there are more to get
    ret = [f"{'101' if lresult == 100 else lresult}"]
    for bmapset in result:
        if bmapset["ChildrenBeatmaps"] is None:
            continue

        # some mirrors use a true/false instead of 0 or 1
        bmapset["HasVideo"] = int(bmapset["HasVideo"])

        diff_sorted_maps = sorted(
            bmapset["ChildrenBeatmaps"],
            key=lambda m: m["DifficultyRating"],
        )

        def handle_invalid_characters(s: str) -> str:
            # XXX: this is a bug that exists on official servers (lmao)
            # | is used to delimit the set data, so the difficulty name
            # cannot contain this or it will be ignored. we fix it here
            # by using a different character.
            return s.replace("|", "I")

        diffs_str = ",".join(
            [
                DIRECT_MAP_INFO_FMTSTR.format(
                    DifficultyRating=row["DifficultyRating"],
                    DiffName=handle_invalid_characters(row["DiffName"]),
                    CS=row["CS"],
                    OD=row["OD"],
                    AR=row["AR"],
                    HP=row["HP"],
                    Mode=row["Mode"],
                )
                for row in diff_sorted_maps
            ],
        )

        ret.append(
            DIRECT_SET_INFO_FMTSTR.format(
                Artist=handle_invalid_characters(bmapset["Artist"]),
                Title=handle_invalid_characters(bmapset["Title"]),
                Creator=bmapset["Creator"],
                RankedStatus=bmapset["RankedStatus"],
                LastUpdate=bmapset["LastUpdate"],
                SetID=bmapset["SetID"],
                HasVideo=bmapset["HasVideo"],
                diffs=diffs_str,
            ),
        )

    return Response("\n".join(ret).encode())


# TODO: video support (needs db change)
@router.get("/web/osu-search-set.php")
@error_catcher
async def osuSearchSetHandler(
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
    map_set_id: Annotated[int | None, Query(alias="s")] = None,
    map_id: Annotated[int | None, Query(alias="b")] = None,
    checksum: Annotated[str | None, Query(alias="c")] = None,
) -> Response:
    # Since we only need set-specific data, we can basically
    # just do same query with either bid or bsid.

    v: int | str
    if map_set_id is not None:
        # this is just a normal request
        k, v = ("set_id", map_set_id)
    elif map_id is not None:
        k, v = ("id", map_id)
    elif checksum is not None:
        k, v = ("md5", checksum)
    else:
        return Response(b"")  # invalid args

    # Get all set data.
    # nosec B608: k is validated to be one of "set_id", "id", or "md5"
    bmapset = await app.state.services.database.fetch_one(
        "SELECT DISTINCT set_id, artist, "
        "title, status, creator, last_update "
        f"FROM maps WHERE {k} = :v",  # nosec B608
        {"v": v},
    )
    if bmapset is None:
        # TODO: get from osu!
        return Response(b"")

    rating = 10.0  # TODO: real data

    return Response(
        (
            "{set_id}.osz|{artist}|{title}|{creator}|"
            "{status}|{rating:.1f}|{last_update}|{set_id}|"
            "0|0|0|0|0"
        )
        .format(**bmapset, rating=rating)
        .encode(),
    )
    # 0s are threadid, has_vid, has_story, filesize, filesize_novid


def chart_entry(name: str, before: float | None, after: float | None) -> str:
    return f"{name}Before:{before or ''}|{name}After:{after or ''}"


def format_achievement_string(file: str, name: str, description: str) -> str:
    return f"{file}+{name}+{description}"


def parse_form_data_score_params(
    score_data: FormData,
) -> tuple[bytes, StarletteUploadFile] | None:
    """Parse the score data, and replay file
    from the form data's 'score' parameters."""
    try:
        score_parts = score_data.getlist("score")
        assert len(score_parts) == 2, "Invalid score data"

        score_data_b64 = score_data.getlist("score")[0]
        if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in [
            "all",
            "scores",
        ]:
            log(f"Score Data b64: {score_data_b64}", Ansi.LMAGENTA)
        assert isinstance(score_data_b64, str), "Invalid score data"
        replay_file = score_data.getlist("score")[1]
        assert isinstance(replay_file, StarletteUploadFile), "Invalid replay data"
    except AssertionError as exc:
        log(f"Failed to validate score multipart data: ({exc.args[0]})", Ansi.LRED)
        return None
    else:
        return (
            score_data_b64.encode(),
            replay_file,
        )


@router.post("/web/osu-submit-modular.php")
@router.post("/web/osu-submit-modular-selector.php")
@error_catcher
async def osuSubmitModularSelector(
    request: Request,
    # TODO: should token be allowed
    # through but ac'd if not found?
    # TODO: validate token format
    # TODO: save token in the database
    token: str | None = Header(None),
    # TODO: do ft & st contain pauses?
    exited_out: bool | None = Form(None, alias="x"),
    fail_time: int | None = Form(None, alias="ft"),
    visual_settings_b64: bytes | None = Form(None, alias="fs"),
    updated_beatmap_hash: str | None = Form(None, alias="bmk"),
    storyboard_md5: str | None = Form(None, alias="sbk"),
    iv_b64: bytes | None = Form(None, alias="iv"),
    unique_ids: str | None = Form(None, alias="c1"),
    score_time: int | None = Form(None, alias="st"),
    pw_md5: str | None = Form(None, alias="pass"),
    osu_version: str | None = Form(None, alias="osuver"),
    client_hash_b64: bytes | None = Form(None, alias="s"),
    fl_cheat_screenshot: bytes | None = File(None, alias="i"),
    # TODO: Process Cheat Values
    cheat_values: str | None = Form(None, alias="cv"),
) -> Response:
    """Handle a score submission from an osu! client with an active session."""

    log(f"Score submission received from {request.url.path}", Ansi.LCYAN)

    # If the request is from the old client endpoint and CHEAT_SERVER is disabled, 404.
    if (
        request.url.path == "/web/osu-submit-modular.php"
        and not app.settings.CHEAT_SERVER
    ):
        log("Old client endpoint disabled, returning 404", Ansi.LYELLOW)
        return Response(b"", status_code=404)

    if app.settings.DEBUG_LEVEL >= 1 and app.settings.DEBUG_FOCUS in ["all", "scores"]:
        if request.url.path == "/web/osu-submit-modular.php":
            log("Received Score Submission from Old Client", Ansi.LMAGENTA)

    if fl_cheat_screenshot:
        if app.settings.DEBUG_LEVEL >= 1 and app.settings.DEBUG_FOCUS in [
            "all",
            "scores",
        ]:
            log("Process FL Screenshot", Ansi.LMAGENTA)
        stacktrace = app.utils.get_appropriate_stacktrace()
        await app.state.services.log_strange_occurrence(stacktrace)

    if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in ["all", "scores"]:
        log("handle score parameters", Ansi.LMAGENTA)
    # NOTE: the bancho protocol uses the "score" parameter name for both
    # the base64'ed score data, and the replay file in the multipart
    # starlette/fastapi do not support this, so we've moved it out
    score_parameters = parse_form_data_score_params(await request.form())
    if score_parameters is None:
        if app.settings.DEBUG_LEVEL >= 1 and app.settings.DEBUG_FOCUS in [
            "all",
            "scores",
        ]:
            log("Score_Parameters is None", Ansi.LMAGENTA)
        return Response(b"")

    # extract the score data and replay file from the score data
    score_data_b64, replay_file = score_parameters

    log("Parsing score data from submission", Ansi.LCYAN)

    # decrypt the score data (aes)
    # Handle None values for required parameters
    if client_hash_b64 is None or iv_b64 is None or osu_version is None:
        log("Missing required parameters for score decryption", Ansi.LRED)
        return Response(b"error: invalid score data")

    log("Decrypting score data", Ansi.LCYAN)
    score_data, client_hash_decoded = encryption.decrypt_score_aes_data(
        score_data_b64,
        client_hash_b64,
        iv_b64,
        osu_version,
    )

    log(f"Score data decrypted, length: {len(score_data)}", Ansi.LCYAN)

    # fetch map & player

    bmap_md5 = score_data[0]
    log(f"Looking up beatmap with MD5: {bmap_md5}", Ansi.LCYAN)
    bmap = await Beatmap.from_md5(bmap_md5)
    if not bmap:
        # Map does not exist, most likely unsubmitted.
        log(f"Beatmap not found for MD5: {bmap_md5}", Ansi.LYELLOW)
        return Response(b"error: beatmap")

    log(f"Beatmap found: {bmap.full_name} (ID: {bmap.id})", Ansi.LCYAN)

    # if the client has supporter, a space is appended
    # but usernames may also end with a space, which must be preserved
    username = score_data[1]
    if username[-1] == " ":
        username = username[:-1]

    log(f"Looking up player: {username}", Ansi.LCYAN)

    if pw_md5 is None:
        log("Password MD5 is None", Ansi.LRED)
        return Response(b"error: invalid score data")

    player = await app.state.sessions.players.from_login(username, pw_md5)
    if not player:
        # Player is not online, return nothing so that their
        # client will retry submission when they log in.
        log(f"Player not found or not online: {username}", Ansi.LYELLOW)
        return Response(b"")

    log(f"Player found: {player.name} (ID: {player.id})", Ansi.LCYAN)

    # parse the score from the remaining data
    log("Parsing score from submission data", Ansi.LCYAN)
    score: Score = Score.from_submission(score_data[2:])

    # attach bmap & player
    score.bmap = bmap
    score.player = player

    log(
        f"Score parsed: {score.mode!r} on {bmap.full_name} by {player.name}",
        Ansi.LCYAN,
    )

    ## perform checksum validation

    log("Performing checksum validation", Ansi.LCYAN)

    if unique_ids is None:
        log("Unique IDs are None", Ansi.LRED)
        return Response(b"error: invalid score data")

    unique_id1, unique_id2 = unique_ids.split("|", maxsplit=1)
    unique_id1_md5 = hashlib.md5(unique_id1.encode(), usedforsecurity=False).hexdigest()
    unique_id2_md5 = hashlib.md5(unique_id2.encode(), usedforsecurity=False).hexdigest()

    log(
        f"Unique IDs validated: {unique_id1_md5[:8]}... / {unique_id2_md5[:8]}...",
        Ansi.LCYAN,
    )

    try:
        assert player.client_details is not None

        log("Validating client details", Ansi.LCYAN)

        if osu_version != f"{player.client_details.osu_version.date:%Y%m%d}":
            raise ValueError(
                f"osu! version mismatch: expected {player.client_details.osu_version.date:%Y%m%d}, got {osu_version}",
            )

        if (
            client_hash_decoded.replace("runningunderwine", "runningunderwine.")
            if "runningunderwine" in client_hash_decoded
            else client_hash_decoded
        ) != player.client_details.client_hash:
            raise ValueError(
                f"client hash mismatch: expected {player.client_details.client_hash}, got {client_hash_decoded.replace('runningunderwine', 'runningunderwine.') if 'runningunderwine' in client_hash_decoded else client_hash_decoded}",
            )

        # assert unique ids (c1) are correct and match login params
        if unique_id1_md5 != player.client_details.uninstall_md5:
            raise ValueError(
                f"unique_id1 mismatch ({unique_id1_md5} != {player.client_details.uninstall_md5})",
            )

        if unique_id2_md5 != player.client_details.disk_signature_md5:
            raise ValueError(
                f"unique_id2 mismatch ({unique_id2_md5} != {player.client_details.disk_signature_md5})",
            )

        # assert online checksums match
        server_score_checksum = score.compute_online_checksum(
            osu_version=osu_version,
            osu_client_hash=client_hash_decoded,
            storyboard_checksum=storyboard_md5 or "",
        )
        if score.client_checksum != server_score_checksum:
            raise ValueError(
                f"online score checksum mismatch ({server_score_checksum} != {score.client_checksum})",
            )

        # assert beatmap hashes match
        if bmap_md5 != updated_beatmap_hash:
            raise ValueError(
                f"beatmap hash mismatch ({bmap_md5} != {updated_beatmap_hash})",
            )

        log("All checksum validations passed", Ansi.LGREEN)

    except (ValueError, AssertionError) as e:
        # NOTE: this is undergoing a temporary trial period,
        # after which, it will be enabled & perform restrictions.
        log(f"Checksum validation failed: {e}", Ansi.LRED)
        stacktrace = app.utils.get_appropriate_stacktrace()
        if app.settings.CHEAT_SERVER:
            log(
                f"{player} submitted a strange score, {e}",
                Ansi.LYELLOW,
                extra={
                    "strange_score": json.dumps(
                        {
                            "player": str(player.name),
                            "bmap_md5": str(bmap_md5),
                            "error": str(e),
                        },
                    ),
                },
            )
        else:
            await app.state.services.log_strange_occurrence(stacktrace)

        # await player.restrict(
        #     admin=app.state.sessions.bot,
        #     reason="mismatching hashes on score submission",
        # )

        # refresh their client state
        # if player.online:
        #     player.logout()

        # return b"error: ban"

    # we should update their activity no matter
    # what the result of the score submission is.
    assert score.player is not None
    score.player.update_latest_activity_soon()

    # make sure the player's client displays the correct mode's stats
    if score.mode != score.player.status.mode:
        score.player.status.mods = score.mods
        score.player.status.mode = score.mode

        if not score.player.restricted:
            app.state.sessions.players.enqueue(app.packets.user_stats(score.player))

    # hold a lock around (check if submitted, submission) to ensure no duplicates
    # are submitted to the database, and potentially award duplicate score/pp/etc.
    async with app.state.score_submission_locks[score.client_checksum]:
        # stop here if this is a duplicate score
        if await app.state.services.database.fetch_one(
            "SELECT 1 FROM scores WHERE online_checksum = :checksum",
            {"checksum": score.client_checksum},
        ):
            log(f"{score.player} submitted a duplicate score.", Ansi.LYELLOW)
            return Response(b"error: no")

        # all data read from submission.
        # now we can calculate things based on our data.
        log("Calculating score accuracy", Ansi.LCYAN)
        score.acc = score.calculate_accuracy()
        log(f"Score accuracy: {score.acc:.2f}%", Ansi.LCYAN)

        log("Checking if osu file is available", Ansi.LCYAN)
        osu_file_available = await ensure_osu_file_is_available(
            bmap.id,
            expected_md5=bmap.md5,
        )

        if osu_file_available:
            log("Calculating performance points", Ansi.LCYAN)
            score.pp, score.sr = score.calculate_performance(bmap.id)
            log(f"Score PP: {score.pp:.2f}, SR: {score.sr:.2f}", Ansi.LCYAN)

            if score.passed:
                log("Calculating score status", Ansi.LCYAN)
                await score.calculate_status()
                log(f"Score status: {score.status!r}", Ansi.LCYAN)

                if score.bmap.status != RankedStatus.Pending:
                    log("Calculating score placement", Ansi.LCYAN)
                    score.rank = await score.calculate_placement()
                    log(f"Score rank: #{score.rank}", Ansi.LCYAN)
            else:
                score.status = SubmissionStatus.FAILED
                log("Score failed", Ansi.LYELLOW)

            score.time_elapsed = (
                int(score_time)
                if score.passed and score_time is not None
                else int(fail_time)
                if fail_time is not None
                else 0
            )
            log(f"Score time elapsed: {score.time_elapsed}ms", Ansi.LCYAN)

        # TODO: re-implement pp caps for non-whitelisted players?

        """ Score submission checks completed; submit the score. """

        log("Score validation complete, submitting to database", Ansi.LCYAN)

        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.submitted_scores")  # type: ignore[no-untyped-call]

        if score.status == SubmissionStatus.BEST:
            log("Score is new personal best", Ansi.LGREEN)

            if app.state.services.datadog:
                app.state.services.datadog.increment("bancho.submitted_scores_best")  # type: ignore[no-untyped-call]

            if score.bmap.has_leaderboard:
                if score.bmap.status == RankedStatus.Loved and score.mode in (
                    GameMode.VANILLA_OSU,
                    GameMode.VANILLA_TAIKO,
                    GameMode.VANILLA_CATCH,
                    GameMode.VANILLA_MANIA,
                ):
                    performance = f"{score.score:,} score"
                else:
                    performance = f"{score.pp:,.2f}pp"

                log(
                    f"Sending achievement notification: #{score.rank} ({performance})",
                    Ansi.LCYAN,
                )
                score.player.enqueue(
                    app.packets.notification(
                        f"You achieved #{score.rank}! ({performance})",
                    ),
                )

                if score.rank == 1 and not score.player.restricted:
                    log("Score is #1, announcing to #announce channel", Ansi.LGREEN)
                    announce_chan = app.state.sessions.channels.get_by_name("#announce")

                    ann = [
                        f"\x01ACTION achieved #1 on {score.bmap.embed}",
                        f"with {score.acc:.2f}% for {performance}.",
                    ]

                    if score.mods:
                        ann.insert(1, f"+{score.mods!r}")

                    scoring_metric = (
                        "pp" if score.mode >= GameMode.RELAX_OSU else "score"
                    )

                    # If there was previously a score on the map, add old #1.
                    prev_n1 = await app.state.services.database.fetch_one(
                        "SELECT u.id, name FROM users u "
                        "INNER JOIN scores s ON u.id = s.userid "
                        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                        "AND s.status = 2 AND u.priv & 1 "
                        f"ORDER BY s.{scoring_metric} DESC LIMIT 1",  # nosec B608
                        {"map_md5": score.bmap.md5, "mode": score.mode},
                    )

                    if prev_n1:
                        if score.player.id != prev_n1["id"]:
                            ann.append(
                                f"(Previous #1: [https://{app.settings.DOMAIN}/u/"
                                "{id} {name}])".format(
                                    id=prev_n1["id"],
                                    name=prev_n1["name"],
                                ),
                            )

                    assert announce_chan is not None
                    announce_chan.send(" ".join(ann), sender=score.player, to_self=True)

            # this score is our best score.
            # update any preexisting personal best
            # records with SubmissionStatus.SUBMITTED.
            log("Updating previous best scores to submitted status", Ansi.LCYAN)
            await app.state.services.database.execute(
                "UPDATE scores SET status = 1 "
                "WHERE status = 2 AND map_md5 = :map_md5 "
                "AND userid = :user_id AND mode = :mode",
                {
                    "map_md5": score.bmap.md5,
                    "user_id": score.player.id,
                    "mode": score.mode,
                },
            )

        log("Inserting score into database", Ansi.LCYAN)
        score.id = await app.state.services.database.execute(
            "INSERT INTO scores "
            "VALUES (NULL, "
            ":map_md5, :score, :pp, :acc, "
            ":max_combo, :mods, :n300, :n100, "
            ":n50, :nmiss, :ngeki, :nkatu, "
            ":grade, :status, :mode, :play_time, "
            ":time_elapsed, :client_flags, :user_id, :perfect, "
            ":checksum, 0)",
            {
                "map_md5": score.bmap.md5,
                "score": score.score,
                "pp": score.pp,
                "acc": score.acc,
                "max_combo": score.max_combo,
                "mods": score.mods,
                "n300": score.n300,
                "n100": score.n100,
                "n50": score.n50,
                "nmiss": score.nmiss,
                "ngeki": score.ngeki,
                "nkatu": score.nkatu,
                "grade": score.grade.name,
                "status": score.status,
                "mode": score.mode,
                "play_time": score.server_time,
                "time_elapsed": score.time_elapsed,
                "client_flags": score.client_flags,
                "user_id": score.player.id,
                "perfect": score.perfect,
                "checksum": score.client_checksum,
            },
        )
        log(f"Score inserted with ID: {score.id}", Ansi.LGREEN)

    if score.passed:
        log("Score passed, handling replay file", Ansi.LCYAN)
        replay_data = await replay_file.read()
        log(f"Replay data size: {len(replay_data)} bytes", Ansi.LCYAN)

        MIN_REPLAY_SIZE = 24

        if len(replay_data) >= MIN_REPLAY_SIZE:
            replay_disk_file = REPLAYS_PATH / f"{score.id}.osr"
            replay_disk_file.write_bytes(replay_data)
            log(f"Replay saved to: {replay_disk_file}", Ansi.LGREEN)
        else:
            log(f"{score.player} submitted a score without a replay!", Ansi.LRED)

            if not score.player.restricted:
                log(
                    f"Restricting player {score.player.name} for submitting score without replay",
                    Ansi.LRED,
                )
                await score.player.restrict(
                    admin=app.state.sessions.bot,
                    reason="submitted score with no replay",
                )
                if score.player.is_online:
                    log(
                        f"Logging out player {score.player.name} after restriction",
                        Ansi.LRED,
                    )
                    score.player.logout()

    """ Update the user's & beatmap's stats """

    log("Updating player and beatmap statistics", Ansi.LCYAN)

    # Get all-time stats (always updated)
    all_time_stats = score.player.stats[score.mode]
    all_time_prev = copy.copy(all_time_stats)

    log(
        f"Previous all-time stats - PP: {all_time_prev.pp}, Acc: {all_time_prev.acc:.2f}%, Plays: {all_time_prev.plays}",
        Ansi.LCYAN,
    )

    # Calculate deltas for this score
    delta_playtime = score.time_elapsed // 1000
    delta_plays = 1
    delta_tscore = score.score
    delta_total_hits = score.n300 + score.n100 + score.n50

    if score.mode.as_vanilla in (1, 3):
        # taiko uses geki & katu for hitting big notes with 2 keys
        # mania uses geki & katu for rainbow 300 & 200
        delta_total_hits += score.ngeki + score.nkatu

    # Update all-time stats with deltas
    all_time_stats.playtime += delta_playtime
    all_time_stats.plays += delta_plays
    all_time_stats.tscore += delta_tscore
    all_time_stats.total_hits += delta_total_hits

    all_time_updates: dict[str, Any] = {
        "plays": all_time_stats.plays,
        "playtime": all_time_stats.playtime,
        "tscore": all_time_stats.tscore,
        "total_hits": all_time_stats.total_hits,
    }

    log(
        f"All-time stats updated - Plays: {all_time_stats.plays}, Playtime: {all_time_stats.playtime}s, Total Score: {all_time_stats.tscore}",
        Ansi.LCYAN,
    )

    # Track grade changes for all-time stats
    delta_grades: dict[Grade, int] = dict.fromkeys(Grade, 0)
    delta_rscore = 0
    delta_max_combo = 0

    if score.passed and score.bmap.has_leaderboard:
        # player passed & map is ranked, approved, or loved.
        log("Score passed on ranked map, updating ranked stats", Ansi.LCYAN)

        if score.max_combo > all_time_stats.max_combo:
            delta_max_combo = score.max_combo - all_time_stats.max_combo
            all_time_stats.max_combo = score.max_combo
            all_time_updates["max_combo"] = all_time_stats.max_combo
            log(f"New max combo: {all_time_stats.max_combo}", Ansi.LCYAN)

        if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
            # map is ranked or approved, and it's our (new)
            # best score on the map. update the player's
            # ranked score, grades, pp, acc and global rank.
            log("Updating ranked score, grades, pp, acc and rank", Ansi.LCYAN)

            additional_rscore = score.score
            if score.prev_best:
                # we previously had a score, so remove
                # it's score from our ranked score.
                additional_rscore -= score.prev_best.score

                if score.grade != score.prev_best.grade:
                    if score.grade >= Grade.A:
                        delta_grades[score.grade] += 1
                        all_time_stats.grades[score.grade] += 1
                        grade_col = format(score.grade, "stats_column")
                        all_time_updates[grade_col] = all_time_stats.grades[score.grade]
                        log(
                            f"Grade changed: {score.prev_best.grade} -> {score.grade}",
                            Ansi.LCYAN,
                        )

                    if score.prev_best.grade >= Grade.A:
                        delta_grades[score.prev_best.grade] -= 1
                        all_time_stats.grades[score.prev_best.grade] -= 1
                        grade_col = format(score.prev_best.grade, "stats_column")
                        all_time_updates[grade_col] = all_time_stats.grades[
                            score.prev_best.grade
                        ]
            else:
                # this is our first submitted score on the map
                if score.grade >= Grade.A:
                    delta_grades[score.grade] += 1
                    all_time_stats.grades[score.grade] += 1
                    grade_col = format(score.grade, "stats_column")
                    all_time_updates[grade_col] = all_time_stats.grades[score.grade]
                    log(f"First score on map, grade: {score.grade.name}", Ansi.LCYAN)

            delta_rscore = additional_rscore
            all_time_stats.rscore += additional_rscore
            all_time_updates["rscore"] = all_time_stats.rscore
            log(
                f"Ranked score updated: +{additional_rscore} (total: {all_time_stats.rscore})",
                Ansi.LCYAN,
            )

            # fetch scores sorted by pp for total acc/pp calc
            # NOTE: we select all plays (and not just top100)
            # because bonus pp counts the total amount of ranked
            # scores. I'm aware this scales horribly, and it'll
            # likely be split into two queries in the future.
            log("Fetching best scores for weighted pp/acc calculation", Ansi.LCYAN)
            best_scores = await app.state.services.database.fetch_all(
                "SELECT s.pp, s.acc FROM scores s "
                "INNER JOIN maps m ON s.map_md5 = m.md5 "
                "WHERE s.userid = :user_id AND s.mode = :mode "
                "AND s.status = 2 AND m.status IN (2, 3) "  # ranked, approved
                "ORDER BY s.pp DESC",
                {"user_id": score.player.id, "mode": score.mode},
            )

            log(
                f"Found {len(best_scores or [])} best scores for calculation",
                Ansi.LCYAN,
            )

            # calculate new total weighted accuracy
            weighted_acc = sum(
                row["acc"] * 0.95**i for i, row in enumerate(best_scores or [])
            )
            bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(best_scores or [])))
            all_time_stats.acc = (weighted_acc * bonus_acc) / 100
            all_time_updates["acc"] = all_time_stats.acc
            log(f"Weighted accuracy calculated: {all_time_stats.acc:.2f}%", Ansi.LCYAN)

            # calculate new total weighted pp
            weighted_pp = sum(
                row["pp"] * 0.95**i for i, row in enumerate(best_scores or [])
            )
            bonus_pp = 416.6667 * (1 - 0.9994 ** len(best_scores or []))
            all_time_stats.pp = round(weighted_pp + bonus_pp)
            all_time_updates["pp"] = all_time_stats.pp
            log(f"Weighted PP calculated: {all_time_stats.pp:.2f}pp", Ansi.LCYAN)

            # update global & country ranking
            log("Updating player rank", Ansi.LCYAN)
            all_time_stats.rank = await score.player.update_rank(score.mode)
            log(f"Player rank updated: #{all_time_stats.rank}", Ansi.LCYAN)

    log("Updating all-time stats in database", Ansi.LCYAN)
    await stats_repo.partial_update(
        score.player.id,
        score.mode.value,
        plays=all_time_updates.get("plays", UNSET),
        playtime=all_time_updates.get("playtime", UNSET),
        tscore=all_time_updates.get("tscore", UNSET),
        total_hits=all_time_updates.get("total_hits", UNSET),
        max_combo=all_time_updates.get("max_combo", UNSET),
        xh_count=all_time_updates.get("xh_count", UNSET),
        x_count=all_time_updates.get("x_count", UNSET),
        sh_count=all_time_updates.get("sh_count", UNSET),
        s_count=all_time_updates.get("s_count", UNSET),
        a_count=all_time_updates.get("a_count", UNSET),
        rscore=all_time_updates.get("rscore", UNSET),
        acc=all_time_updates.get("acc", UNSET),
        pp=all_time_updates.get("pp", UNSET),
    )
    log("All-time stats updated in database", Ansi.LGREEN)

    # Update season stats if seasons are enabled
    log("Checking if seasons are enabled", Ansi.LCYAN)

    # Store season stats BEFORE update for chart generation
    season_stats_before_map: dict[int, dict[str, Any]] = {}

    try:
        seasons_enabled = await app.state.services.database.fetch_val(
            "SELECT value FROM server_data WHERE type = 'seasons_enabled'",
        )
        if seasons_enabled == "1":
            log("Seasons are enabled, updating season stats", Ansi.LCYAN)

            # Get default schedule
            default_schedule = await seasons_repo.fetch_default_schedule()

            # Collect all season IDs that need to be updated
            seasons_to_update: set[int] = set()

            # 1. Add active season for default schedule (always)
            if default_schedule:
                default_active_season = (
                    await seasons_repo.fetch_active_season_by_schedule(
                        default_schedule["id"],
                    )
                )
                if (
                    default_active_season
                    and default_active_season["start_date"]
                    <= score.server_time
                    < default_active_season["end_date"]
                ):
                    seasons_to_update.add(default_active_season["id"])
                    log(
                        f"Will update default schedule active season: {default_active_season['id']}",
                        Ansi.LCYAN,
                    )

            # 2. Add active season for player's preferred schedule (if different from default)
            if score.player.preferred_schedule_id is not None and (
                default_schedule is None
                or score.player.preferred_schedule_id != default_schedule["id"]
            ):
                preferred_active_season = (
                    await seasons_repo.fetch_active_season_by_schedule(
                        score.player.preferred_schedule_id,
                    )
                )
                if (
                    preferred_active_season
                    and preferred_active_season["start_date"]
                    <= score.server_time
                    < preferred_active_season["end_date"]
                ):
                    seasons_to_update.add(preferred_active_season["id"])
                    log(
                        f"Will update player's preferred schedule active season: {preferred_active_season['id']}",
                        Ansi.LCYAN,
                    )

            # Fetch season stats BEFORE updating them (for chart generation)
            # This must happen BEFORE the stats are updated to capture the "before" state
            for season_id in seasons_to_update:
                try:
                    season_info = await seasons_repo.fetch_one(id=season_id)
                    if not season_info:
                        continue

                    existing = await stats_repo.fetch_one(
                        player_id=score.player.id,
                        mode=score.mode.value,
                        season_id=season_id,
                    )
                    if existing:
                        # Store a copy of the stats BEFORE update
                        season_stats_before_map[season_id] = dict(existing.items())
                        log(
                            f"Stored season {season_id} stats BEFORE update for chart: pp={existing['pp']}, acc={existing['acc']}",
                            Ansi.LCYAN,
                        )
                except Exception as e:
                    log(
                        f"Failed to fetch season stats before update: {e}",
                        Ansi.LYELLOW,
                    )

            # Update each season with deltas
            for season_id in seasons_to_update:
                log(f"Updating season stats for season {season_id}", Ansi.LCYAN)
                try:
                    # Fetch the season to get its date range
                    season_info = await seasons_repo.fetch_one(id=season_id)
                    if not season_info:
                        log(f"Season {season_id} not found, skipping", Ansi.LYELLOW)
                        continue

                    existing = await stats_repo.fetch_one(
                        player_id=score.player.id,
                        mode=score.mode.value,
                        season_id=season_id,
                    )
                    if existing is None:
                        log(
                            f"Creating season stats rows for player {score.player.id}",
                            Ansi.LCYAN,
                        )
                        await stats_repo.create_all_modes_for_season(
                            player_id=score.player.id,
                            season_id=season_id,
                        )
                        # Fetch again after creation
                        existing = await stats_repo.fetch_one(
                            player_id=score.player.id,
                            mode=score.mode.value,
                            season_id=season_id,
                        )

                    if existing:
                        # Apply deltas to season stats
                        season_updates: dict[str, Any] = {
                            "plays": existing["plays"] + delta_plays,
                            "playtime": existing["playtime"] + delta_playtime,
                            "tscore": existing["tscore"] + delta_tscore,
                            "total_hits": existing["total_hits"] + delta_total_hits,
                        }

                        if delta_max_combo > 0:
                            season_updates["max_combo"] = max(
                                existing["max_combo"],
                                all_time_stats.max_combo,
                            )

                        if delta_rscore != 0:
                            season_updates["rscore"] = existing["rscore"] + delta_rscore

                        # Apply grade deltas
                        for grade, delta in delta_grades.items():
                            if delta != 0:
                                grade_col = format(grade, "stats_column")
                                season_updates[grade_col] = (
                                    cast(int, existing.get(grade_col, 0)) + delta
                                )

                        # For pp and acc, we need to recalculate for the season
                        # Fetch best scores for this season to calculate weighted pp/acc
                        log(
                            f"Recalculating weighted pp/acc for season {season_id}",
                            Ansi.LCYAN,
                            level=logLevel.DEBUG,
                        )
                        season_best_scores = await app.state.services.database.fetch_all(
                            "SELECT pp, acc FROM ("
                            "SELECT s.pp, s.acc, "
                            "ROW_NUMBER() OVER (PARTITION BY s.map_md5 ORDER BY s.pp DESC) AS rn "
                            "FROM scores s "
                            "INNER JOIN maps m ON s.map_md5 = m.md5 "
                            "WHERE s.userid = :user_id AND s.mode = :mode "
                            "AND s.status >= 1 AND m.status IN (2, 3) "
                            "AND s.play_time >= :season_start AND s.play_time < :season_end"
                            ") ranked WHERE rn = 1 "
                            "ORDER BY pp DESC",
                            {
                                "user_id": score.player.id,
                                "mode": score.mode,
                                "season_start": season_info["start_date"],
                                "season_end": season_info["end_date"],
                            },
                        )

                        if season_best_scores:
                            # calculate new total weighted accuracy for season
                            season_weighted_acc = sum(
                                row["acc"] * 0.95**i
                                for i, row in enumerate(season_best_scores)
                            )
                            season_bonus_acc = 100.0 / (
                                20 * (1 - 0.95 ** len(season_best_scores))
                            )
                            season_acc = (season_weighted_acc * season_bonus_acc) / 100
                            season_updates["acc"] = season_acc
                            log(
                                f"Season weighted accuracy calculated: {season_acc:.2f}% (from {len(season_best_scores)} scores)",
                                Ansi.LCYAN,
                                level=logLevel.DEBUG,
                            )

                            # calculate new total weighted pp for season
                            season_weighted_pp = sum(
                                row["pp"] * 0.95**i
                                for i, row in enumerate(season_best_scores)
                            )
                            season_bonus_pp = 416.6667 * (
                                1 - 0.9994 ** len(season_best_scores)
                            )
                            season_pp = round(season_weighted_pp + season_bonus_pp)
                            season_updates["pp"] = season_pp
                            log(
                                f"Season weighted PP calculated: {season_pp:.2f}pp (from {len(season_best_scores)} scores)",
                                Ansi.LCYAN,
                                level=logLevel.DEBUG,
                            )
                        else:
                            # No scores in season yet, use current score values
                            season_updates["pp"] = score.pp
                            season_updates["acc"] = score.acc
                            log(
                                f"No season scores found, using current score values: pp={score.pp:.2f}, acc={score.acc:.2f}%",
                                Ansi.LCYAN,
                                level=logLevel.DEBUG,
                            )

                        await stats_repo.partial_update(
                            score.player.id,
                            score.mode.value,
                            season_id=season_id,
                            **season_updates,
                        )
                        log(
                            f"Season {season_id} stats updated with deltas",
                            Ansi.LGREEN,
                        )
                except Exception as e:
                    log(
                        f"Failed to update season stats for season {season_id}: {e}",
                        Ansi.LRED,
                        level=logLevel.ERROR,
                    )
        else:
            log("Seasons are not enabled", Ansi.LCYAN)
    except Exception as e:
        log(
            f"Failed to fetch seasons for score submission: {e}",
            Ansi.LRED,
            level=logLevel.ERROR,
        )

    if not score.player.restricted:
        # enqueue new stats info to all other users
        log("Sending updated stats to other players", Ansi.LCYAN)
        app.state.sessions.players.enqueue(app.packets.user_stats(score.player))

        # update beatmap with new stats
        log("Updating beatmap statistics", Ansi.LCYAN)
        score.bmap.plays += 1
        if score.passed:
            score.bmap.passes += 1
            log(f"Beatmap passes updated: {score.bmap.passes}", Ansi.LCYAN)

        await app.state.services.database.execute(
            "UPDATE maps SET plays = :plays, passes = :passes WHERE md5 = :map_md5",
            {
                "plays": score.bmap.plays,
                "passes": score.bmap.passes,
                "map_md5": score.bmap.md5,
            },
        )
        log(
            f"Beatmap stats updated - Plays: {score.bmap.plays}, Passes: {score.bmap.passes}",
            Ansi.LCYAN,
        )

    # update their recent score
    score.player.recent_scores[score.mode] = score
    log("Updated player's recent score", Ansi.LCYAN)

    """ score submission charts """

    log("Generating score submission response", Ansi.LCYAN)

    # charts are only displayed for passes vanilla gamemodes.
    if not score.passed:  # TODO: check if this is correct
        log("Score failed, returning error response", Ansi.LYELLOW)
        response = b"error: no"
    else:
        log("Score passed, generating achievement and ranking charts", Ansi.LCYAN)

        # construct and send achievements & ranking charts to the client
        if score.bmap.awards_ranked_pp and not score.player.restricted:
            log("Checking for unlocked achievements", Ansi.LCYAN)
            unlocked_achievements: list[Achievement] = []

            server_achievements = await achievements_usecases.fetch_many()
            player_achievements = await user_achievements_usecases.fetch_many(
                user_id=score.player.id,
            )

            log(
                f"Checking {len(server_achievements)} server achievements against {len(player_achievements)} player achievements",
                Ansi.LCYAN,
            )

            for server_achievement in server_achievements:
                player_unlocked_achievement = any(
                    player_achievement
                    for player_achievement in player_achievements
                    if player_achievement["achid"] == server_achievement["id"]
                )
                if player_unlocked_achievement:
                    # player already has this achievement.
                    continue

                achievement_condition = server_achievement["cond"]
                if achievement_condition(score, score.mode.as_vanilla):
                    log(
                        f"Achievement unlocked: {server_achievement['name']}",
                        Ansi.LGREEN,
                    )
                    await user_achievements_usecases.create(
                        score.player.id,
                        server_achievement["id"],
                    )
                    unlocked_achievements.append(server_achievement)

            achievements_str = "/".join(
                format_achievement_string(a["file"], a["name"], a["desc"])
                for a in unlocked_achievements
            )
            log(
                f"Total achievements unlocked: {len(unlocked_achievements)}",
                Ansi.LCYAN,
            )
        else:
            achievements_str = ""
            log(
                "No achievements to check (map doesn't award PP or player is restricted)",
                Ansi.LCYAN,
            )

        # create score submission charts for osu! client to display
        log("Building submission charts", Ansi.LCYAN)

        if score.prev_best:
            log(
                f"Previous best score found - Rank: #{score.prev_best.rank}, PP: {score.prev_best.pp:.2f}",
                Ansi.LCYAN,
            )
            beatmap_ranking_chart_entries = (
                chart_entry("rank", score.prev_best.rank, score.rank),
                chart_entry("rankedScore", score.prev_best.score, score.score),
                chart_entry("totalScore", score.prev_best.score, score.score),
                chart_entry("maxCombo", score.prev_best.max_combo, score.max_combo),
                chart_entry(
                    "accuracy",
                    round(score.prev_best.acc, 2),
                    round(score.acc, 2),
                ),
                chart_entry("pp", score.prev_best.pp, score.pp),
            )
        else:
            # no previous best score
            log("No previous best score found", Ansi.LCYAN)
            beatmap_ranking_chart_entries = (
                chart_entry("rank", None, score.rank),
                chart_entry("rankedScore", None, score.score),
                chart_entry("totalScore", None, score.score),
                chart_entry("maxCombo", None, score.max_combo),
                chart_entry("accuracy", None, round(score.acc, 2)),
                chart_entry("pp", None, score.pp),
            )

        # Determine which stats to use for the overall ranking chart
        # based on the player's preferred view
        chart_stats: ModeData
        chart_prev: ModeData
        using_seasonal_stats = False

        log(
            f"Player {score.player.name} preferred_lb_view: {score.player.preferred_lb_view}",
            Ansi.LCYAN,
        )
        log(
            f"Player {score.player.name} preferred_schedule_id: {score.player.preferred_schedule_id}",
            Ansi.LCYAN,
        )

        if score.player.preferred_lb_view == "seasonal":
            log(f"Player {score.player.name} has seasonal view preference", Ansi.LCYAN)
            # Use seasonal stats for the preferred schedule (or default schedule if no preference)
            seasonal_stats: ModeData | None = None
            seasonal_prev: ModeData | None = None

            # Get the schedule to use (preferred or default)
            schedule_id = score.player.preferred_schedule_id
            log(
                f"Initial schedule_id from player preference: {schedule_id}",
                Ansi.LCYAN,
            )

            if schedule_id is None:
                # No preference, use default schedule
                log("No preferred schedule_id, fetching default schedule", Ansi.LCYAN)
                default_schedule = await seasons_repo.fetch_default_schedule()
                if default_schedule:
                    schedule_id = default_schedule["id"]
                    log(f"Using default schedule_id: {schedule_id}", Ansi.LCYAN)
                else:
                    log("No default schedule found", Ansi.LYELLOW)

            if schedule_id is not None:
                log(
                    f"Looking for active season for schedule_id: {schedule_id}",
                    Ansi.LCYAN,
                )
                # Get the active season for this schedule
                active_season = await seasons_repo.fetch_active_season_by_schedule(
                    schedule_id,
                )
                log(f"Active season result: {active_season}", Ansi.LCYAN)

                if active_season:
                    log(
                        f"Active season found: ID={active_season['id']}, start={active_season['start_date']}, end={active_season['end_date']}",
                        Ansi.LCYAN,
                    )
                    log(f"Score server_time: {score.server_time}", Ansi.LCYAN)

                    # Check if score is within season time range
                    if (
                        active_season["start_date"]
                        <= score.server_time
                        < active_season["end_date"]
                    ):
                        log("Score is within active season time range", Ansi.LGREEN)

                        # Get the PREVIOUS stats for this season (stored before the update)
                        log(
                            f"Using stored PREVIOUS season stats for player {score.player.id}, mode {score.mode.value}, season {active_season['id']}",
                            Ansi.LCYAN,
                        )
                        season_stats_before = season_stats_before_map.get(
                            active_season["id"],
                        )
                        log(
                            f"Season stats BEFORE update result: {season_stats_before}",
                            Ansi.LCYAN,
                        )

                        if season_stats_before:
                            log(
                                "Season stats BEFORE update found, converting to ModeData for seasonal_prev",
                                Ansi.LGREEN,
                            )
                            # Convert to ModeData format for the PREVIOUS stats
                            seasonal_prev = ModeData(
                                tscore=season_stats_before["tscore"],
                                rscore=season_stats_before["rscore"],
                                pp=season_stats_before["pp"],
                                acc=season_stats_before["acc"],
                                plays=season_stats_before["plays"],
                                playtime=season_stats_before["playtime"],
                                max_combo=season_stats_before["max_combo"],
                                total_hits=season_stats_before["total_hits"],
                                rank=0,  # Will be calculated if needed
                                grades={
                                    Grade.XH: season_stats_before["xh_count"],
                                    Grade.X: season_stats_before["x_count"],
                                    Grade.SH: season_stats_before["sh_count"],
                                    Grade.S: season_stats_before["s_count"],
                                    Grade.A: season_stats_before["a_count"],
                                },
                            )
                            log(
                                f"Seasonal PREV stats created: pp={seasonal_prev.pp}, acc={seasonal_prev.acc:.2f}%, plays={seasonal_prev.plays}",
                                Ansi.LCYAN,
                            )
                        else:
                            log(
                                f"No season stats found BEFORE update for player {score.player.id} in season {active_season['id']}",
                                Ansi.LYELLOW,
                            )
                            # Create empty previous stats
                            seasonal_prev = ModeData(
                                tscore=0,
                                rscore=0,
                                pp=0,
                                acc=0.0,
                                plays=0,
                                playtime=0,
                                max_combo=0,
                                total_hits=0,
                                rank=0,
                                grades=dict.fromkeys(Grade, 0),
                            )
                            log("Created empty seasonal_prev stats", Ansi.LCYAN)

                        # Now fetch the UPDATED stats (after the season stats update above)
                        log(
                            f"Fetching UPDATED season stats for player {score.player.id}, mode {score.mode.value}, season {active_season['id']}",
                            Ansi.LCYAN,
                        )
                        season_stats_after = await stats_repo.fetch_one(
                            player_id=score.player.id,
                            mode=score.mode.value,
                            season_id=active_season["id"],
                        )
                        log(
                            f"Season stats AFTER update result: {season_stats_after}",
                            Ansi.LCYAN,
                        )

                        if season_stats_after:
                            log(
                                "Season stats AFTER update found, converting to ModeData for seasonal_stats",
                                Ansi.LGREEN,
                            )
                            # Convert to ModeData format for the UPDATED stats
                            seasonal_stats = ModeData(
                                tscore=season_stats_after["tscore"],
                                rscore=season_stats_after["rscore"],
                                pp=season_stats_after["pp"],
                                acc=season_stats_after["acc"],
                                plays=season_stats_after["plays"],
                                playtime=season_stats_after["playtime"],
                                max_combo=season_stats_after["max_combo"],
                                total_hits=season_stats_after["total_hits"],
                                rank=0,  # Will be calculated if needed
                                grades={
                                    Grade.XH: season_stats_after["xh_count"],
                                    Grade.X: season_stats_after["x_count"],
                                    Grade.SH: season_stats_after["sh_count"],
                                    Grade.S: season_stats_after["s_count"],
                                    Grade.A: season_stats_after["a_count"],
                                },
                            )
                            log(
                                f"Seasonal stats AFTER update created: pp={seasonal_stats.pp}, acc={seasonal_stats.acc:.2f}%, plays={seasonal_stats.plays}",
                                Ansi.LCYAN,
                            )

                            # Calculate and update the season rank
                            log(
                                f"Calculating season rank for player {score.player.id}, mode {score.mode.value}, season {active_season['id']}",
                                Ansi.LCYAN,
                            )
                            try:
                                # Update the season leaderboard in Redis
                                await score.player.update_season_rank(
                                    active_season["id"],
                                    score.mode,
                                )
                                # Get the calculated rank
                                seasonal_rank = await score.player.get_season_rank(
                                    active_season["id"],
                                    score.mode,
                                )
                                seasonal_stats.rank = seasonal_rank
                                seasonal_prev.rank = seasonal_rank  # Set prev rank to same (since we don't track rank changes)
                                log(
                                    f"Season rank calculated: #{seasonal_rank}",
                                    Ansi.LCYAN,
                                )
                            except Exception as e:
                                log(f"Failed to calculate season rank: {e}", Ansi.LRED)
                                seasonal_stats.rank = 0
                                seasonal_prev.rank = 0
                        else:
                            log(
                                f"No season stats found AFTER update for player {score.player.id} in season {active_season['id']}",
                                Ansi.LYELLOW,
                            )
                    else:
                        log(
                            f"Score is NOT within active season time range (score_time: {score.server_time}, season: {active_season['start_date']} to {active_season['end_date']})",
                            Ansi.LYELLOW,
                        )
                else:
                    log(
                        f"No active season found for schedule_id {schedule_id}",
                        Ansi.LYELLOW,
                    )
            else:
                log(
                    "No schedule_id available (neither preferred nor default)",
                    Ansi.LYELLOW,
                )

            # If we couldn't get seasonal stats, fall back to all-time stats
            if seasonal_stats is not None and seasonal_prev is not None:
                log("Using seasonal stats for chart", Ansi.LGREEN)
                chart_stats = seasonal_stats
                chart_prev = seasonal_prev
                using_seasonal_stats = True
            else:
                log("Falling back to all-time stats for chart", Ansi.LYELLOW)
                chart_stats = all_time_stats
                chart_prev = all_time_prev
        else:
            log(
                f"Player {score.player.name} does not have seasonal view preference (using all-time)",
                Ansi.LCYAN,
            )
            # Use all-time stats
            chart_stats = all_time_stats
            chart_prev = all_time_prev

        log(
            f"Final chart_stats source: {'seasonal' if using_seasonal_stats else 'all-time'}",
            Ansi.LCYAN,
        )
        log(
            f"Chart stats - pp: {chart_stats.pp:.2f}, acc: {chart_stats.acc:.2f}%, plays: {chart_stats.plays}",
            Ansi.LCYAN,
        )
        log(
            f"Chart prev - pp: {chart_prev.pp:.2f}, acc: {chart_prev.acc:.2f}%, plays: {chart_prev.plays}",
            Ansi.LCYAN,
        )

        overall_ranking_chart_entries = (
            chart_entry("rank", chart_prev.rank, chart_stats.rank),
            chart_entry("rankedScore", chart_prev.rscore, chart_stats.rscore),
            chart_entry("totalScore", chart_prev.tscore, chart_stats.tscore),
            chart_entry("maxCombo", chart_prev.max_combo, chart_stats.max_combo),
            chart_entry(
                "accuracy",
                round(chart_prev.acc, 2),
                round(chart_stats.acc, 2),
            ),
            chart_entry("pp", chart_prev.pp, chart_stats.pp),
        )

        log(
            f"Overall ranking changes - Rank: #{chart_prev.rank} -> #{chart_stats.rank}, PP: {chart_prev.pp:.2f} -> {chart_stats.pp:.2f}",
            Ansi.LCYAN,
        )

        submission_charts = [
            # beatmap info chart
            f"beatmapId:{score.bmap.id}",
            f"beatmapSetId:{score.bmap.set_id}",
            f"beatmapPlaycount:{score.bmap.plays}",
            f"beatmapPasscount:{score.bmap.passes}",
            f"approvedDate:{score.bmap.last_update}",
            "\n",
            # beatmap ranking chart
            "chartId:beatmap",
            f"chartUrl:{score.bmap.set.url}",
            "chartName:Beatmap Ranking",
            *beatmap_ranking_chart_entries,
            f"onlineScoreId:{score.id}",
            "\n",
            # overall ranking chart
            "chartId:overall",
            f"chartUrl:https://{app.settings.DOMAIN}/u/{score.player.id}",
            "chartName:Overall Ranking",
            *overall_ranking_chart_entries,
            f"achievements-new:{achievements_str}",
        ]

        response = "|".join(submission_charts).encode()
        log(
            f"Submission charts generated, response length: {len(response)} bytes",
            Ansi.LCYAN,
        )

    if app.settings.CHEAT_SERVER:
        if cheat_values:
            if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in [
                "all",
                "scores",
            ]:
                log(
                    f"Cheat Values: {cheat_values}",
                    Ansi.GRAY,
                    extra={"Cheat_Values": cheat_values},
                )

            # Validate that cheat_values is valid JSON
            try:
                # Try to parse the cheat_values as JSON to validate it
                parsed_cheat_values = json.loads(cheat_values)

                # If it's valid JSON, serialize it back to a string for database storage
                # This ensures consistent formatting and prevents double-encoding issues
                cheat_values_str = json.dumps(parsed_cheat_values)

                if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in [
                    "all",
                    "scores",
                ]:
                    log(f"Score ID: {score.id}, Score Status: {score.status}")

                if (score.status == 2) or (
                    score.status > 0 and score.id and score.id != 0
                ):
                    if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in [
                        "all",
                        "scores",
                    ]:
                        log(f"Score ID: {score.id}")

                    print("Inserting Cheat Values")
                    await app.state.services.database.execute(
                        "INSERT INTO scoreinfo (scoreid, cheat_values) "
                        "VALUES (:scoreid, :cheat_values)",
                        {
                            "scoreid": score.id,
                            "cheat_values": cheat_values_str,
                        },
                    )
            except json.JSONDecodeError as e:
                # If cheat_values is not valid JSON, log the error and don't save it
                log(
                    f"Invalid JSON in cheat_values: {e}",
                    Ansi.LRED,
                    extra={
                        "score_id": score.id,
                        "player": str(score.player),
                        "invalid_cheat_values": cheat_values,
                    },
                )
                # Optionally, you could also restrict the player for submitting invalid data
                # if not score.player.restricted:
                #     await score.player.restrict(
                #         admin=app.state.sessions.bot,
                #         reason="submitted score with invalid cheat_values JSON",
                #     )
            except Exception as e:
                log(f"Error Inserting Cheat Values: {e}", Ansi.LRED)
                # Continue processing - error is already logged
    log(
        f"[{score.mode!r}] {score.player} submitted a score! "
        f"({score.status!r}, {score.pp:,.2f}pp / {all_time_stats.pp:,}pp)",
        Ansi.LGREEN,
        extra={
            "Score": json.dumps(
                {
                    "score_id": score.id,
                    "map_md5": score.bmap.md5,
                    "score": score.score,
                    "pp": score.pp,
                    "acc": score.acc,
                    "max_combo": score.max_combo,
                    "mods": f"{score.mods!r}",
                    "n300": score.n300,
                    "n100": score.n100,
                    "n50": score.n50,
                    "nmiss": score.nmiss,
                    "ngeki": score.ngeki,
                    "nkatu": score.nkatu,
                    "grade": score.grade.name,
                    "status": f"{score.status!r}",
                    "mode": f"{score.mode!r}",
                    "client_flags": score.client_flags,
                    "cheat_values": cheat_values,
                },
            ),
            "Player": json.dumps(
                {
                    "id": score.player.id,
                    "name": score.player.name,
                },
            ),
        },
    )

    log("Score submission complete, returning response to client", Ansi.LGREEN)
    log(f"Final response length: {len(response)} bytes", Ansi.LCYAN)

    # TODO: execute write log in a way that is non blocking
    if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in ["all", "scores"]:
        if request.url.path == "/web/osu-submit-modular.php":
            clientfolder = "oldclients"
        else:
            clientfolder = "newclients"
        dir = SystemPath.cwd() / f".data/logs/scores/{clientfolder}"
        file_path = f"{dir}/submission{score.id}.log"
        if not dir.exists():
            dir.mkdir(parents=True)

        # Create the file if it doesn't exist
        if not os.path.exists(file_path):
            open(file_path, "a").close()

        # Execute Write Log
        asyncio.create_task(app.utils.write_log_file("SCORE", file_path, request))  # type: ignore[unused-awaitable]

    return Response(response)


@router.get("/web/osu-getreplay.php")
@error_catcher
async def getReplay(
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
    mode: Annotated[int, Query(..., alias="m", ge=0, le=3)],
    score_id: Annotated[
        int,
        Query(..., alias="c", min=0, max=9_223_372_036_854_775_807),
    ],
) -> Response:
    score = await Score.from_sql(score_id)
    if not score:
        return Response(b"", status_code=404)

    file = REPLAYS_PATH / f"{score_id}.osr"
    if not file.exists():
        return Response(b"", status_code=404)

    # increment replay views for this score
    if score.player is not None and player.id != score.player.id:
        app.state.loop.create_task(score.increment_replay_views())  # type: ignore[unused-awaitable]

    return FileResponse(file)


@router.get("/web/osu-rate.php")
@error_catcher
async def osuRate(
    player: Annotated[
        Player,
        Depends(authenticate_player_session(Query, "u", "p", err=b"auth fail")),
    ],
    map_md5: Annotated[str, Query(..., alias="c", min_length=32, max_length=32)],
    rating: Annotated[int | None, Query(alias="v", ge=1, le=10)] = None,
) -> Response:
    if rating is None:
        # check if we have the map in our cache;
        # if not, the map probably doesn't exist.
        if map_md5 not in app.state.cache.beatmap:
            return Response(b"no exist")

        cached = app.state.cache.beatmap[map_md5]

        # only allow rating on maps with a leaderboard.
        if cached.status < RankedStatus.Ranked:
            return Response(b"not ranked")

        # osu! client is checking whether we can rate the map or not.
        # the client hasn't rated the map, so simply
        # tell them that they can submit a rating.
        if not await ratings_repo.fetch_one(map_md5=map_md5, userid=player.id):
            return Response(b"ok")
    else:
        # the client is submitting a rating for the map.
        await ratings_repo.create(userid=player.id, map_md5=map_md5, rating=rating)

    map_ratings = await ratings_repo.fetch_many(map_md5=map_md5)
    ratings = [row["rating"] for row in map_ratings]

    # send back the average rating
    avg = sum(ratings) / len(ratings)
    return Response(f"alreadyvoted\n{avg}".encode())


@unique
@pymysql_encode(escape_enum)
class LeaderboardType(IntEnum):
    Local = 0
    Top = 1
    Mods = 2
    Friends = 3
    Country = 4


async def get_leaderboard_scores(
    leaderboard_type: LeaderboardType | int,
    map_md5: str,
    mode: int,
    mods: Mods,
    player: Player,
    scoring_metric: Literal["pp", "score"],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    # Check if seasons are enabled and player prefers seasonal view
    season_start_date: datetime | None = None
    season_end_date: datetime | None = None

    try:
        seasons_enabled = await app.state.services.database.fetch_val(
            "SELECT value FROM server_data WHERE type = 'seasons_enabled'",
        )
        if seasons_enabled == "1" and player.preferred_lb_view == "seasonal":
            # Determine which season to use
            if player.selected_season_id is not None:
                # Player has selected a specific season
                season = await seasons_repo.fetch_one(id=player.selected_season_id)
            else:
                # Use active season type
                season = await seasons_repo.fetch_active_season_by_type()

            if season:
                season_start_date = season["start_date"]
                season_end_date = season["end_date"]
    except Exception as e:
        log(
            f"Failed to fetch season for leaderboard: {e}",
            Ansi.LRED,
            level=logLevel.ERROR,
        )

    query = [
        f"SELECT s.id, s.{scoring_metric} AS _score, "  # nosec B608
        "s.max_combo, s.n50, s.n100, s.n300, "
        "s.nmiss, s.nkatu, s.ngeki, s.perfect, s.mods, "
        "UNIX_TIMESTAMP(s.play_time) time, u.id userid, "
        "COALESCE(CONCAT('[', c.tag, '] ', u.name), u.name) AS name "
        "FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "LEFT JOIN clans c ON c.id = u.clan_id "
        "WHERE s.map_md5 = :map_md5 AND s.status = 2 "  # 2: =best score
        "AND (u.priv & 1 OR u.id = :user_id) AND mode = :mode",
    ]

    params: dict[str, Any] = {
        "map_md5": map_md5,
        "user_id": player.id,
        "mode": mode,
    }

    # Add season filtering if applicable
    if season_start_date is not None and season_end_date is not None:
        query.append("AND s.play_time >= :season_start AND s.play_time < :season_end")
        params["season_start"] = season_start_date
        params["season_end"] = season_end_date

    if leaderboard_type == LeaderboardType.Mods:
        query.append("AND s.mods = :mods")
        params["mods"] = mods
    elif leaderboard_type == LeaderboardType.Friends:
        query.append("AND s.userid IN :friends")
        params["friends"] = player.friends | {player.id}
    elif leaderboard_type == LeaderboardType.Country:
        query.append("AND u.country = :country")
        params["country"] = player.geoloc["country"]["acronym"]

    # TODO: customizability of the number of scores
    query.append("ORDER BY _score DESC LIMIT 50")

    score_rows = await app.state.services.database.fetch_all(
        " ".join(query),
        params,
    )

    if score_rows:  # None or []
        # fetch player's personal best score
        personal_best_query = [
            f"SELECT id, {scoring_metric} AS _score, "  # nosec B608
            "max_combo, n50, n100, n300, "
            "nmiss, nkatu, ngeki, perfect, mods, "
            "UNIX_TIMESTAMP(play_time) time "
            "FROM scores "
            "WHERE map_md5 = :map_md5 AND mode = :mode "
            "AND userid = :user_id AND status = 2 ",
        ]

        personal_best_params: dict[str, Any] = {
            "map_md5": map_md5,
            "mode": mode,
            "user_id": player.id,
        }

        # Add season filtering if applicable
        if season_start_date is not None and season_end_date is not None:
            personal_best_query.append(
                "AND play_time >= :season_start AND play_time < :season_end",
            )
            personal_best_params["season_start"] = season_start_date
            personal_best_params["season_end"] = season_end_date

        personal_best_query.append("ORDER BY _score DESC LIMIT 1")

        personal_best_score_row = await app.state.services.database.fetch_one(
            " ".join(personal_best_query),
            personal_best_params,
        )

        if personal_best_score_row is not None:
            # calculate the rank of the score.
            rank_query = [
                "SELECT COUNT(*) FROM scores s "
                "INNER JOIN users u ON u.id = s.userid "
                "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                "AND s.status = 2 AND u.priv & 1 "
                f"AND s.{scoring_metric} > :score",  # nosec B608
            ]

            rank_params: dict[str, Any] = {
                "map_md5": map_md5,
                "mode": mode,
                "score": personal_best_score_row["_score"],
            }

            # Add season filtering if applicable
            if season_start_date is not None and season_end_date is not None:
                rank_query.append(
                    "AND s.play_time >= :season_start AND s.play_time < :season_end",
                )
                rank_params["season_start"] = season_start_date
                rank_params["season_end"] = season_end_date

            p_best_rank = 1 + int(
                await app.state.services.database.fetch_val(
                    " ".join(rank_query),
                    rank_params,
                    column=0,  # COUNT(*)
                ),
            )

            # attach rank to personal best row
            personal_best_score_row["rank"] = p_best_rank
    else:
        score_rows = []
        personal_best_score_row = None

    return score_rows, personal_best_score_row


SCORE_LISTING_FMTSTR = (
    "{id}|{name}|{score}|{max_combo}|"
    "{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|"
    "{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}"
)


@router.get("/web/osu-osz2-getscores.php")
@error_catcher
async def getScores(
    request: Request,
    player: Annotated[Player, Depends(authenticate_player_session(Query, "us", "ha"))],
    requesting_from_editor_song_select: Annotated[bool, Query(..., alias="s")],
    leaderboard_version: Annotated[int, Query(..., alias="vv")],
    leaderboard_type: Annotated[int, Query(..., alias="v", ge=0, le=4)],
    map_md5: Annotated[str, Query(..., alias="c", min_length=32, max_length=32)],
    map_filename: Annotated[str, Query(..., alias="f")],
    mode_arg: Annotated[int, Query(..., alias="m", ge=0, le=3)],
    map_set_id: Annotated[int, Query(..., alias="i", ge=-1, le=2_147_483_647)],
    mods_arg: Annotated[int, Query(..., alias="mods", ge=0, le=2_147_483_647)],
    map_package_hash: Annotated[str, Query(..., alias="h")],  # TODO: further validation
    aqn_files_found: Annotated[bool, Query(..., alias="a")],
) -> Response:
    if app.settings.DEBUG_LEVEL >= 2 and app.settings.DEBUG_FOCUS in [
        "all",
        "leaderboards",
    ]:
        log(
            f"""Player: {player}
              Requesting from editor: {requesting_from_editor_song_select}
              Leaderboard version: {leaderboard_version}
              Leaderboard type: {leaderboard_type}
              Map md5: {map_md5}
              Map filename: {map_filename}
              Mode arg: {mode_arg}
              Map set id: {map_set_id}
              Mods arg: {mods_arg}
              Map package hash: {map_package_hash}
              AQN files found: {aqn_files_found}""",
            Ansi.LMAGENTA,
        )
    if aqn_files_found:
        stacktrace = app.utils.get_appropriate_stacktrace()
        await app.state.services.log_strange_occurrence(stacktrace)

    # check if this md5 has already been  cached as
    # unsubmitted/needs update to reduce osu!api spam
    if map_md5 in app.state.cache.unsubmitted:
        return Response(b"-1|false")
    if map_md5 in app.state.cache.needs_update:
        return Response(b"1|false")

    if mods_arg & Mods.RELAX:
        if mode_arg == 3:  # rx!mania doesn't exist
            mods_arg &= ~Mods.RELAX
        else:
            mode_arg += 4
    elif mods_arg & Mods.AUTOPILOT:
        if mode_arg in (1, 2, 3):  # ap!catch, taiko and mania don't exist
            mods_arg &= ~Mods.AUTOPILOT
        else:
            mode_arg += 8

    mods = Mods(mods_arg)
    mode = GameMode(mode_arg)

    # attempt to update their stats if their
    # gm/gm-affecting-mods change at all.
    if mode != player.status.mode:
        player.status.mods = mods
        player.status.mode = mode

        if not player.restricted:
            app.state.sessions.players.enqueue(app.packets.user_stats(player))

    scoring_metric: Literal["pp", "score"] = (
        "pp" if mode >= GameMode.RELAX_OSU else "score"
    )

    bmap = await Beatmap.from_md5(map_md5, set_id=map_set_id)
    has_set_id = map_set_id > 0

    if not bmap:
        # map not found, figure out whether it needs an
        # update or isn't submitted using its filename.

        if has_set_id and map_set_id not in app.state.cache.beatmapset:
            # set not cached, it doesn't exist
            app.state.cache.unsubmitted.add(map_md5)
            return Response(b"-1|false")

        map_filename = unquote_plus(map_filename)  # TODO: is unquote needed?

        map_exists = False
        if has_set_id:
            # we can look it up in the specific set from cache
            for bmap in app.state.cache.beatmapset[map_set_id].maps:
                if map_filename == bmap.filename:
                    map_exists = True
                    break
            else:
                map_exists = False
        else:
            # we can't find it on the osu!api by md5,
            # and we don't have the set id, so we must
            # look it up in sql from the filename.
            map_exists = (
                await maps_repo.fetch_one(
                    filename=map_filename,
                )
                is not None
            )

        if map_exists:
            # map can be updated.
            app.state.cache.needs_update.add(map_md5)
            return Response(b"1|false")
        else:
            # map is unsubmitted.
            # add this map to the unsubmitted cache, so
            # that we don't have to make this request again.
            app.state.cache.unsubmitted.add(map_md5)
            return Response(b"-1|false")

    # we've found a beatmap for the request.

    if app.state.services.datadog:
        app.state.services.datadog.increment("bancho.leaderboards_served")  # type: ignore[no-untyped-call]

    if bmap.status < RankedStatus.Ranked:
        # only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return Response(f"{int(bmap.status)}|false".encode())

    # fetch scores & personal best
    # TODO: create a leaderboard cache
    if not requesting_from_editor_song_select:
        score_rows, personal_best_score_row = await get_leaderboard_scores(
            leaderboard_type,
            bmap.md5,
            mode,
            mods,
            player,
            scoring_metric,
        )
    else:
        score_rows = []
        personal_best_score_row = None

    # fetch beatmap rating
    map_ratings = await ratings_repo.fetch_many(
        map_md5=bmap.md5,
        page=None,
        page_size=None,
    )
    ratings = [row["rating"] for row in map_ratings]
    map_avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    ## construct response for osu! client

    response_lines: list[str] = [
        # NOTE: fa stands for featured artist (for the ones that may not know)
        # {ranked_status}|{serv_has_osz2}|{bid}|{bsid}|{len(scores)}|{fa_track_id}|{fa_license_text}
        f"{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{len(score_rows)}|0|",
        # {offset}\n{beatmap_name}\n{rating}
        # TODO: server side beatmap offsets
        f"0\n{bmap.full_name}\n{map_avg_rating}",
    ]

    if not score_rows:
        response_lines.extend(("", ""))  # no scores, no personal best
        return Response("\n".join(response_lines).encode())

    if personal_best_score_row is not None:
        user_clan = (
            await clans_repo.fetch_one(id=player.clan_id)
            if player.clan_id is not None
            else None
        )
        display_name = (
            f"[{user_clan['tag']}] {player.name}"
            if user_clan is not None
            else player.name
        )
        response_lines.append(
            SCORE_LISTING_FMTSTR.format(
                **personal_best_score_row,
                name=display_name,
                userid=player.id,
                score=int(round(personal_best_score_row["_score"])),
                has_replay="1",
            ),
        )
    else:
        response_lines.append("")

    response_lines.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **s,
                score=int(round(s["_score"])),
                has_replay="1",
                rank=idx + 1,
            )
            for idx, s in enumerate(score_rows)
        ],
    )

    # Add Requested Score and other information to request.state.func_info
    request.state.req_info = {}
    try:
        request.state.req_info = {
            "request_type": "Leaderboard",
            "player_requesting": f"<{player.id}> {player.name}",
            "requested_leaderboard": {
                "map_name": bmap.full_name,
                "map_md5": map_md5,
                "map_set_id": bmap.set_id,
                "map_id": bmap.id,
                "map_status": bmap.status,
                "map_avg_rating": map_avg_rating,
                "leaderboard_type": leaderboard_type,
                "leaderboard_version": leaderboard_version,
                "leaderboard_score_count": len(score_rows),
                "leaderboard": score_rows,
            },
        }
    except Exception as e:
        request.state.req_info = {
            "error": f"Error in setting request.state.req_info: {e}",
            "function": "getScores",
            "file": "/app/api/domains/osu.py",
        }
        pass

    return Response("\n".join(response_lines).encode())


# TODO: Investigate Byte Consumption in End State from Old Clients
@router.post("/web/osu-comment.php")
@error_catcher
async def osuComment(
    player: Annotated[Player, Depends(authenticate_player_session(Form, "u", "p"))],
    map_id: Annotated[int, Form(..., alias="b")],
    map_set_id: Annotated[int, Form(..., alias="s")],
    score_id: Annotated[int, Form(..., alias="r", ge=0, le=9_223_372_036_854_775_807)],
    mode_vn: Annotated[int, Form(..., alias="m", ge=0, le=3)],
    action: Annotated[Literal["get", "post"], Form(..., alias="a")],
    # only sent for post
    target: Annotated[Literal["song", "map", "replay"] | None, Form()] = None,
    colour: Annotated[
        str | None,
        Form(alias="f", min_length=6, max_length=6),
    ] = None,
    start_time: Annotated[int | None, Form(alias="starttime")] = None,
    comment: Annotated[str | None, Form(min_length=1, max_length=80)] = None,
) -> Response:
    if action == "get":
        # client is requesting all comments
        comments = await comments_repo.fetch_all_relevant_to_replay(
            score_id=score_id,
            map_set_id=map_set_id,
            map_id=map_id,
        )

        ret: list[str] = []

        for cmt in comments:
            # note: this implementation does not support
            #       "player" or "creator" comment colours
            if cmt["priv"] & Privileges.NOMINATOR:
                fmt = "bat"
            elif cmt["priv"] & Privileges.DONATOR:
                fmt = "supporter"
            else:
                fmt = ""

            if cmt["colour"]:
                fmt += f"|{cmt['colour']}"

            ret.append(
                "{time}\t{target_type}\t{fmt}\t{comment}".format(fmt=fmt, **cmt),
            )

        player.update_latest_activity_soon()
        return Response("\n".join(ret).encode())

    elif action == "post":
        # client is submitting a new comment

        # validate all required params are provided
        assert target is not None
        assert start_time is not None
        assert comment is not None

        # get the corresponding id from the request
        if target == "song":
            target_id = map_set_id
        elif target == "map":
            target_id = map_id
        else:  # target == "replay"
            target_id = score_id

        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            colour = None

            log(
                f"User {player} attempted to use a coloured comment without "
                "supporter status. Submitting comment without a colour.",
            )

        # insert into sql
        await comments_repo.create(
            target_id=target_id,
            target_type=comments_repo.TargetType(target),
            userid=player.id,
            time=start_time,
            comment=comment,
            colour=colour,
        )

        player.update_latest_activity_soon()

    return Response(b"")  # empty resp is fine


@router.get("/web/osu-markasread.php")
@error_catcher
async def osuMarkAsRead(
    player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
    channel: Annotated[str, Query(..., min_length=0, max_length=32)],
) -> Response:
    target_name = unquote(channel)  # TODO: unquote needed?
    if not target_name:
        log(
            f"User {player} attempted to mark a channel as read without a target.",
            Ansi.LYELLOW,
        )
        return Response(b"")  # no channel specified

    target = await app.state.sessions.players.from_cache_or_sql(name=target_name)
    if target:
        # mark any unread mail from this user as read.
        await mail_repo.mark_conversation_as_read(
            to_id=player.id,
            from_id=target.id,
        )

    return Response(b"")


@router.get("/web/osu-getseasonal.php")
@error_catcher
async def osuSeasonal() -> Response:
    return ORJSONResponse(app.settings.SEASONAL_BGS)


# TODO: Investigate and Fix byte consumption in End State from Old Clients
@router.get("/web/bancho_connect.php")
@error_catcher
async def banchoConnect(
    # NOTE: this is disabled as this endpoint can be called
    #       before a player has been granted a session
    # player: Annotated[Player, Depends(authenticate_player_session(Query, "u", "h"))],
    osu_ver: Annotated[str, Query(..., alias="v")],
    active_endpoint: Annotated[str | None, Query(alias="fail")] = None,
    net_framework_vers: Annotated[
        str | None,
        Query(alias="fx"),
    ] = None,  # delimited by |
    client_hash: Annotated[str | None, Query(alias="ch")] = None,
    retrying: Annotated[bool | None, Query(alias="retry")] = None,  # '0' or '1'
) -> Response:
    return Response(b"")


@router.get("/web/check-updates.php")
@error_catcher
async def checkUpdates(
    request: Request,
    action: Annotated[Literal["check", "path", "error"], Query(...)],
    stream: Annotated[
        Literal["cuttingedge", "stable40", "beta40", "stable"],
        Query(...),
    ],
) -> Response:
    return Response(b"")


""" Misc handlers """


def fileMd5(file_path: str) -> str:
    with open(file_path, "rb") as file:
        md5_hash = hashlib.md5(usedforsecurity=False)  # nosec B324
        for chunk in iter(lambda: file.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


if app.settings.REDIRECT_OSU_URLS:
    # NOTE: this will likely be removed with the addition of a frontend.
    async def osu_redirect(request: Request, _: int = Path(...)) -> Response:
        return RedirectResponse(
            url=f"https://osu.ppy.sh{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    for pattern in (
        "/beatmapsets/{_}",
        "/beatmaps/{_}",
        "/beatmapsets/{_}/discussion",
        "/community/forums/topics/{_}",
    ):
        router.get(pattern)(osu_redirect)


@router.get("/ss/{screenshot_id}.{extension}")
@error_catcher
async def get_screenshot(
    screenshot_id: Annotated[str, Path(..., pattern=r"[a-zA-Z0-9-_]{8}")],
    extension: Annotated[Literal["jpg", "jpeg", "png"], Path(...)],
) -> Response:
    """Serve a screenshot from the server, by filename."""
    screenshot_path = SCREENSHOTS_PATH / f"{screenshot_id}.{extension}"

    if not screenshot_path.exists():
        return ORJSONResponse(
            content={"status": "Screenshot not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if extension in ("jpg", "jpeg"):
        media_type = "image/jpeg"
    elif extension == "png":
        media_type = "image/png"
    else:
        media_type = None

    return FileResponse(
        path=screenshot_path,
        media_type=media_type,
    )


@router.get("/d/{map_set_id}")
@error_catcher
async def get_osz(
    map_set_id: Annotated[str, Path(...)],
) -> Response:
    """Handle a map download request (osu.ppy.sh/d/*)."""
    no_video = map_set_id[-1] == "n"
    if no_video:
        map_set_id = map_set_id[:-1]

    query_str = f"{map_set_id}?n={int(not no_video)}"

    return RedirectResponse(
        url=f"{app.settings.MIRROR_DOWNLOAD_ENDPOINT}/{query_str}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get("/web/maps/{map_filename}")
@error_catcher
async def get_updated_beatmap(
    request: Request,
    map_filename: str,
    host: Annotated[str, Header(...)],
) -> Response:
    """Send the latest .osu file the server has for a given map."""
    if host == "osu.ppy.sh":
        return Response("bancho.py only supports the -devserver connection method")

    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['raw_path'].decode()}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get("/p/doyoureallywanttoaskpeppy")
@error_catcher
async def peppyDMHandler() -> Response:
    return Response(
        content=(
            b"This user's ID is usually peppy's (when on bancho), "
            b"and is blocked from being messaged by the osu! client."
        ),
    )


""" ingame registration """

INGAME_REGISTRATION_DISALLOWED_ERROR = {
    "form_error": {
        "user": {
            "password": [
                "In-game registration is disabled. Please register on the website.",
            ],
        },
    },
}


@router.post("/users")
@error_catcher
async def register_account(
    request: Request,
    username: str = Form(..., alias="user[username]"),
    email: str = Form(..., alias="user[user_email]"),
    pw_plaintext: str = Form(..., alias="user[password]"),
    check: int = Form(...),
    # XXX: require/validate these headers; they are used later
    # on in the registration process for resolving geolocation
    forwarded_ip: str = Header(..., alias="X-Forwarded-For"),
    real_ip: str = Header(..., alias="X-Real-IP"),
) -> Response:
    if not all((username, email, pw_plaintext)):
        return Response(
            content=b"Missing required params",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Disable in-game registration if enabled
    if app.settings.DISALLOW_INGAME_REGISTRATION:
        return ORJSONResponse(
            content=INGAME_REGISTRATION_DISALLOWED_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # ensure all args passed
    # are safe for registration.
    errors: Mapping[str, list[str]] = defaultdict(list)

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    if not regexes.USERNAME.match(username):
        errors["username"].append("Must be 2-15 characters in length.")

    if "_" in username and " " in username:
        errors["username"].append('May contain "_" and " ", but not both.')

    if username in app.settings.DISALLOWED_NAMES:
        errors["username"].append("Disallowed username; pick another.")

    if "username" not in errors:
        if await users_repo.fetch_one(name=username):
            errors["username"].append("Username already taken by another player.")

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.EMAIL.match(email):
        errors["user_email"].append("Invalid email syntax.")
    else:
        if await users_repo.fetch_one(email=email):
            errors["user_email"].append("Email already taken by another player.")

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 <= len(pw_plaintext) <= 32:
        errors["password"].append("Must be 8-32 characters in length.")

    if len(set(pw_plaintext)) <= 3:
        errors["password"].append("Must have more than 3 unique characters.")

    if pw_plaintext.lower() in app.settings.DISALLOWED_PASSWORDS:
        errors["password"].append("That password was deemed too simple.")

    if errors:
        # we have errors to send back, send them back delimited by newlines.
        errors = {k: ["\n".join(v)] for k, v in errors.items()}
        errors_full = {"form_error": {"user": errors}}
        return ORJSONResponse(
            content=errors_full,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if check == 0:
        # the client isn't just checking values,
        # they want to register the account now.
        # make the md5 & bcrypt the md5 for sql.
        pw_md5 = (
            hashlib.md5(pw_plaintext.encode(), usedforsecurity=False)
            .hexdigest()
            .encode()
        )  # nosec B324
        pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
        app.state.cache.bcrypt[pw_bcrypt] = pw_md5  # cache result for login

        ip = app.state.services.ip_resolver.get_ip(request.headers)

        geoloc = await app.state.services.fetch_geoloc(ip, request.headers)
        country = geoloc["country"]["acronym"] if geoloc is not None else "XX"

        async with app.state.services.database.transaction():
            # add to `users` table.
            player = await users_repo.create(
                name=username,
                email=email,
                pw_bcrypt=pw_bcrypt,
                country=country,
            )

            # add to `stats` table.
            await stats_repo.create_all_modes(player_id=player["id"])

        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.registrations")  # type: ignore[no-untyped-call]

        log(f"<{username} ({player['id']})> has registered!", Ansi.LGREEN)

    return Response(content=b"ok")  # success


@router.post("/difficulty-rating")
@error_catcher
async def difficultyRatingHandler(request: Request) -> Response:
    if app.settings.DEBUG_LEVEL >= 3 and app.settings.DEBUG_FOCUS in [
        "all",
        "leaderboards",
    ]:
        # Print the request body
        body = await request.body()
        log(f"Request URL: {request.url}\nRequest Body: {body.decode()}", Ansi.LMAGENTA)

        # Print the request path
        print(f"Request Path: {request.url.path}")

    # Redirect the request
    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['path']}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/web/check-aeris-updates.php")
@router.post("/web/check-aeris-updates.php")
@error_catcher
async def checkAerisUpdates(
    request: Request,
    action: Literal["check", "path", "error", "get-manifest"]
    | None = None,  # "request-put", "put"
    stream: Literal["cuttingedge", "stable40", "beta40", "stable", "dev"] | None = None,
    fileinfo: str | None = None,
    buildname: str | None = None,
    ufile: UploadFile | None = None,
) -> Response:
    neededFiles = [
        "avcodec-51.dll",
        "avformat-52.dll",
        "avutil-49.dll",
        "bass.dll",
        "bass_fx.dll",
        "d3dcompiler_47.dll",
        "DiscordRPC.dll",
        "libEGL.dll",
        "libGLESv2.dll",
        "Microsoft.Ink.dll",
        "Newtonsoft.Json.dll",
        "OpenTK.dll",  #
        "osu!common.dll",  #
        "osu!gameplay.dll",  #
        "osu!ui.dll",
        "osu!.exe",
        "osu.dll",  #
        "pthreadGC2.dll",
        "SmartThreadPool.dll",  #
        "WindowsInput.dll",
    ]
    files_to_exclude = []
    args = {}

    for key, _ in request.query_params.items():
        args[key] = request.query_params[key].lower()
    log(f"[Aeris Updater Debug] Args: {args}")

    if action == "get-manifest":
        try:
            manifest = {}
            updater_cache = f".data/storage/updater/{stream}/updater.json"

            # Load existing manifest if it exists
            if os.path.exists(updater_cache):
                with open(updater_cache) as f:
                    manifest = json.loads(f.read())

            # Convert list to dictionary format for easier lookup
            manifest_dict = {
                "files": {entry["filename"]: entry for entry in manifest},
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                "stream": stream,
            }

            return Response(json.dumps(manifest_dict))
        except Exception as e:
            log(
                f"Error in Aeris Updater Get-Manifest Action: {e}",
                level=logLevel.ERROR,
            )
            return Response(json.dumps({"error": str(e)}))

    #    elif action == "request-put":
    #        try:
    #            # Parse the incoming file info
    #            new_file = json.loads(fileinfo)
    #
    #            # Check if we have a previous version to create patch from
    #            current_file = get_current_file_version(stream, new_file["filename"])
    #            if current_file:
    #                if "build_name" not in current_file:
    #                    current_file["build_name"] = ""
    #                return Response(json.dumps({
    #                    "response": "patch",
    #                    "filename": current_file["filename"],
    #                    "file_hash": current_file["file_hash"],
    #                    "build_name": current_file["build_name"],
    #                    "url_full": f"https://storage.kawata.pw/get/updater/{stream}/zip/{current_file['file_hash']}.zip"
    #                }))
    #
    #            return Response(json.dumps({"response": "ok"}))
    #        except Exception as e:
    #            log(f"Error in Aeris Updater Request-Put Action: {e}", level=logLevel.ERROR)
    #            return Response(json.dumps({"response": f"Error: {e}"}))
    #
    #    elif action == "put":
    #        try:
    #            # Handle file upload
    #            file_data = json.loads(fileinfo)
    #            file_type = request.query_params.get("type", "full")
    #
    #            if file_type == "patch":
    #                base_path = f".data/storage/updater/{stream}/patches"
    #                url_base = f"https://storage.kawata.pw/get/updater/{stream}/patches"
    #            else:
    #                base_path = f".data/storage/updater/{stream}"
    #                url_base = f"https://storage.kawata.pw/get/updater/{stream}"
    #            #upload_path = f".data/storage/updater/{stream}/{file_data['filename']}"
    #            os.makedirs(base_path, exist_ok=True)
    #            if file_type == "patch":
    #                # Patches use hash as filename
    #                file_path = f"{base_path}/{file_data['file_hash']}"
    #            else:
    #                # Full files keep original name
    #                file_path = f"{base_path}/{file_data['filename']}"
    #
    #            # Save uploaded file
    #            with open(file_path, "wb") as f:
    #                f.write(await ufile.read())
    #                log(f"[Aeris Updater Upload] {file_data['build_name']} | {file_data['filename']}", extra={})
    #
    #            if file_type == "patch":
    #                file_data["url_patch"] = f"{url_base}/{file_data['file_hash']}"
    #            else:
    #                file_data["url_full"] = f"{url_base}/{file_data['file_hash']}"
    #                zf = zipfile.ZipFile(".data/storage/updater/{}/zip/{}.zip".format(args["stream"], file_data["file_hash"]), mode='w')
    #                file = ".data/storage/updater/{}/{}".format(args["stream"], file_data['filename'])
    #                zf.write(file, arcname=file_data['filename'])
    #
    #            # Update version database
    #            update_file_version(stream, file_data, file_data['build_name'], request)
    #
    #            return Response(json.dumps({"response": "ok"}))
    #        except Exception as e:
    #            log(f"Error in Aeris Updater Put Action: {e}", level=logLevel.ERROR)
    #            return Response(json.dumps({"response": f"Error: {e}"}))

    if args["stream"].lower() == "dev":
        neededFiles += [
            "osu!.deps.json",
            "osu!.runtimeconfig.json",
            "osu!.Game.dll",
            "osu!.dll",
            "osu!.Resources.dll",
        ]
        files_to_exclude += [
            "SmartThreadPool.dll",
            "osu.dll",
            "OpenTK.dll",
            "DiscordRPC.dll",
            "Newtonsoft.Json.dll",
            "WindowsInput.dll",
        ]
        neededFiles = [file for file in neededFiles if file not in files_to_exclude]
    # if args["stream"].lower() == "cuttingedge":
    #    args["stream"] = "stable40"

    if args["stream"].lower() == "stable":
        neededFiles.append("oppai.exe")

    if args["stream"].lower() == "stable40":
        neededFiles.append("DiscordRPC.dll")

    if args["action"].lower() == "check" or args["action"].lower() == "path":
        try:
            updaterCache = ".data/storage/updater/{}/{}".format(
                args["stream"],
                "updater.json",
            )
            if not os.path.exists(updaterCache):
                needUpdate = True
            result: list[dict[str, Any]] = []
            log("[Aeris updater]: requested Update for : {}".format(args["stream"]))
            data = []
            needUpdate = True
            try:
                data = json.loads(open(updaterCache).read())
                needUpdate = len(data) < len(neededFiles)
                index = 0
                # Add build_name field if missing, Prevents error in upload portion.
                for entry in data:
                    if "build_name" not in entry:
                        entry["build_name"] = ""
                        needUpdate = True
                if needUpdate:
                    # Write back the modified data
                    with open(updaterCache, "w") as f:
                        f.write(json.dumps(data))
                if not needUpdate:
                    for x in neededFiles:
                        timestamp = time.strftime(
                            "%m-%d-%Y %H:%M:%S",
                            time.gmtime(
                                os.path.getmtime(
                                    ".data/storage/updater/{}/{}".format(
                                        args["stream"],
                                        x,
                                    ),
                                ),
                            ),
                        )

                        if data[index]["timestamp"] != timestamp:
                            needUpdate = True
                        index += 1
            except Exception:
                needUpdate = True
            if needUpdate:
                if os.path.exists(
                    ".data/storage/updater/{}/{}".format(args["stream"], "updating"),
                ):
                    log("Still updating, sending cache")
                    return Response(json.dumps(data))
                f = open(
                    ".data/storage/updater/{}/{}".format(args["stream"], "updating"),
                    "w",
                )
                existing_data = {}
                if os.path.exists(updaterCache):
                    try:
                        with open(updaterCache) as f:
                            existing_data = {
                                entry["filename"]: entry
                                for entry in json.loads(f.read())
                            }
                    except Exception:
                        pass  # nosec B110
                try:
                    log(
                        "[Aeris updater] New files detected, updating Downloadable files",
                    )
                    log("[AU] Clearing zip cache")
                except Exception as e:
                    log(f"[AU] Error during zip cache clear: {e}", Ansi.LYELLOW)
                path = ".data/storage/updater/{}/zip".format(args["stream"])
                shutil.rmtree(path)
                os.mkdir(path)
                for x in neededFiles:
                    index = len(result)
                    # Start with existing entry if available
                    result.append(existing_data.get(x, {}))
                    file = ".data/storage/updater/{}/{}".format(args["stream"], x)

                    result[index]["filesize"] = os.stat(file).st_size
                    result[index]["file_hash"] = fileMd5(file)
                    result[index]["url_full"] = (
                        "https://storage.kawata.pw/get/updater/{}/zip/{}".format(
                            args["stream"],
                            result[index]["file_hash"],
                        )
                    )
                    file_timestamp = os.path.getmtime(
                        ".data/storage/updater/{}/{}".format(args["stream"], x),
                    )
                    result[index]["timestamp"] = time.strftime(
                        "%m-%d-%Y %H:%M:%S",
                        time.gmtime(file_timestamp),
                    )
                    result[index]["filename"] = x
                    if "patch_id" not in result[index]:
                        result[index]["patch_id"] = None
                    zf = zipfile.ZipFile(
                        ".data/storage/updater/{}/zip/{}.zip".format(
                            args["stream"],
                            result[index]["file_hash"],
                        ),
                        mode="w",
                    )
                    zf.write(file, arcname=x)
                    f = open(updaterCache, "w")
                    f.write(json.dumps(result))

                os.remove(
                    ".data/storage/updater/{}/{}".format(args["stream"], "updating"),
                )
                log("[Aeris updater] Downloadable files updated")

            else:
                result = data if "data" in locals() else []

            return Response(json.dumps(result))
        except Exception as e:
            log(f"Error: {e}", Ansi.LRED)
            return Response("")
    else:
        log(
            "[Aeris updater] unknown action type : {}".format(args["action"]),
            Ansi.YELLOW,
        )
    return Response(b"")


@router.get("/web/get-internal-version.php")
async def getInternalVersion(v: int) -> Response:
    # Generate an incremental build number
    # Could store this in a database to persist across restarts
    current = get_current_internal_version(v)
    new_version = current + 1
    save_internal_version(v, new_version)

    return Response(str(new_version))


def get_current_file_version(stream: str, filename: str) -> dict[str, Any] | None:
    """Get the current version info for a file in a stream"""
    try:
        updater_cache = f".data/storage/updater/{stream}/updater.json"
        if os.path.exists(updater_cache):
            with open(updater_cache) as f:
                data: list[dict[str, Any]] = json.loads(f.read())
                for file_info in data:
                    if file_info["filename"] == filename:
                        return file_info
    except Exception as e:
        log(f"Error getting current file version: {e}", Ansi.LRED)
    return None


def get_base_filename(filename: str) -> str:
    # If filename contains underscores and hash-like strings, it's a patch
    if filename.count("_") == 2 and len(filename.split("_")[1]) == 32:
        return filename.split("_")[0]
    return filename


def update_file_version(
    stream: str,
    file_data: dict[str, Any],
    build_name: str,
    request: Request,
) -> None:
    """Update version info after successful upload"""
    try:
        updater_cache = f".data/storage/updater/{stream}/updater.json"
        data = []
        if os.path.exists(updater_cache):
            with open(updater_cache) as f:
                data = json.loads(f.read())

        is_patch = "patch" in request.query_params.get("type", "")

        # Update or add new file info
        updated = False
        if is_patch:
            base_filename = get_base_filename(file_data["filename"])
            # Find and update entry using base filename
            for i, file_info in enumerate(data):
                if file_info["filename"] == base_filename:
                    data[i]["url_patch"] = file_data["url_patch"]
                    data[i]["patch_id"] = file_data.get("patch_id")
                    data[i]["patch_from"] = file_data.get("patch_from")
        for i, file_info in enumerate(data):
            if file_info["filename"] == file_data["filename"]:
                if "url_full" not in file_data and "url_full" in file_info:
                    file_data["url_full"] = file_info["url_full"]
                if "url_patch" not in file_data and "url_patch" in file_info:
                    file_data["url_patch"] = file_info["url_patch"]
                data[i] = file_data
                data[i]["build_name"] = build_name
                updated = True
                break

        if not updated:
            file_data["build_name"] = build_name
            data.append(file_data)

        with open(updater_cache, "w") as f:
            json.dump(data, f)

    except Exception as e:
        log(f"Error updating file version: {e}", Ansi.LRED)


def get_current_internal_version(version: int) -> int:
    """Get current internal version number for main version"""
    try:
        version_file = f".data/storage/internal_versions/{version}.txt"
        if os.path.exists(version_file):
            with open(version_file) as f:
                return int(f.read().strip())
    except Exception as e:
        log(f"Error getting internal version: {e}", Ansi.LRED)
    return 0


def save_internal_version(version: int, internal: int) -> None:
    """Save new internal version number"""
    try:
        os.makedirs(".data/storage/internal_versions", exist_ok=True)
        version_file = f".data/storage/internal_versions/{version}.txt"
        with open(version_file, "w") as f:
            f.write(str(internal))
    except Exception as e:
        log(f"Error saving internal version: {e}", Ansi.LRED)


@router.post("/aeris/osu-error.php")
@error_catcher
async def aerisErrorHandler(
    request: Request,
    data: str = Form(..., alias="error"),
) -> Response:
    error_data = json.loads(data)

    # Process based on error type
    submission_types = error_data.get("SubmissionTypes", [])
    if "ES" in submission_types:
        log(
            f"[Aeris Error] {error_data.get('Username')} encountered an error in their client.",
            Ansi.LYELLOW,
            extra={"osu-error": json.dumps(error_data)},
            levelow=True,
        )
    else:
        log(
            f"[Aeris Error] {error_data.get('Username')} encountered frame drops.",
            Ansi.LYELLOW,
            extra={"osu-error": json.dumps(error_data)},
            levelow=True,
        )

    return Response(content=b"Successfully Uploaded Error")
