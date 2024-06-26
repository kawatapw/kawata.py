""" osu: handle connections from web, api, and beyond? """
from __future__ import annotations

import os, shutil, time, zipfile
import copy
import hashlib
import random
import secrets
import json
import asyncio
from base64 import b64decode
from collections import defaultdict
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from enum import IntEnum
from enum import unique
from functools import cache
from pathlib import Path as SystemPath
from typing import Any
from typing import Literal
from typing import Optional
from urllib.parse import unquote
from urllib.parse import unquote_plus

import bcrypt
from fastapi import status
from fastapi.datastructures import FormData
from fastapi.datastructures import UploadFile
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.param_functions import Header
from fastapi.param_functions import Path
from fastapi.param_functions import Query
from fastapi.requests import Request
from fastapi.responses import FileResponse
from fastapi.responses import ORJSONResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter
from py3rijndael import Pkcs7Padding
from py3rijndael import RijndaelCbc
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette import status

import app.packets
import app.settings
import app.state
import app.utils
from app._typing import UNSET
from app.constants import regexes
from app.constants.clientflags import LastFMFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.logging import printc
from app.objects import models
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_local_osu_file
from app.objects.beatmap import RankedStatus
from app.objects.player import Player
from app.objects.score import Grade
from app.objects.score import Score
from app.objects.score import SubmissionStatus
from app.repositories import maps as maps_repo
from app.repositories import players as players_repo
from app.repositories import scores as scores_repo
from app.repositories import stats as stats_repo
from app.repositories.achievements import Achievement
from app.usecases import achievements as achievements_usecases
from app.usecases import user_achievements as user_achievements_usecases
from app.utils import escape_enum
from app.utils import pymysql_encode


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
        player = await app.state.sessions.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
        if player:
            return player

        # player login incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err,  # TODO: make sure this works
        )

    return wrapper


""" /web/ handlers """

# TODO
# POST /web/osu-session.php
# POST /web/osu-osz2-bmsubmit-post.php
# POST /web/osu-osz2-bmsubmit-upload.php
# GET /web/osu-osz2-bmsubmit-getid.php
# GET /web/osu-get-beatmap-topic.php

OsuClientModes = Literal[
    "Menu",
    "Edit",
    "Play",
    "Exit",
    "SelectEdit",
    "SelectPlay",
    "SelectDrawings",
    "Rank",
    "Update",
    "Busy",
    "Unknown",
    "Lobby",
    "MatchSetup",
    "SelectMulti",
    "RankingVs",
    "OnlineSelection",
    "OptionsOffsetWizard",
    "RankingTagCoop",
    "RankingTeam",
    "BeatmapImport",
    "PackageUpdater",
    "Benchmark",
    "Tourney",
    "Charts",
]

OsuClientGameModes = Literal[
    "Osu",
    "Taiko",
    "CatchTheBeat",
    "OsuMania",
]


#@router.post("/web/osu-error.php")
async def osuError(
    username: str | None = Form(None, alias="u"),
    pw_md5: str | None = Form(None, alias="h"),
    user_id: int | None = Form(None, alias="i", ge=3, le=2_147_483_647),
    osu_mode: OsuClientModes | None = Form(None, alias="osumode"),
    game_mode: OsuClientGameModes | None = Form(None, alias="gamemode"),
    game_time: int | None = Form(None, alias="gametime", ge=0),
    audio_time: int | None = Form(None, alias="audiotime"),
    culture: str | None = Form(None),
    map_id: int | None = Form(None, alias="beatmap_id", ge=0, le=2_147_483_647),
    map_md5: str | None = Form(None, alias="beatmap_checksum", min_length=32, max_length=32),
    exception: str | None = Form(None),
    feedback: str | None = Form(None),
    stacktrace: str | None = Form(None),
    soft: bool | None = Form(None),
    map_count: int | None = Form(None, alias="beatmap_count", ge=0),
    compatibility: bool | None = Form(None),
    ram_used: int | None = Form(None, alias="ram", ge=0),
    osu_version: str | None = Form(None, alias="version"),
    exe_hash: str | None = Form(None, alias="exehash"),
    config: str | None = Form(None),
    screenshot_file: UploadFile | None = File(None, alias="ss"),
) -> Response:
    """Handle an error submitted from the osu! client."""
    if not app.settings.DEBUG and not app.settings.DEBUG_CLIENT:
        # only handle osu-error in debug mode
        return Response(b"")

    if username and pw_md5:
        player = await app.state.sessions.players.from_login(
            name=unquote(username),
            pw_md5=pw_md5,
        )
        if not player:
            # player login incorrect
            await app.state.services.log_strange_occurrence("osu-error auth failed")
            player = None
    else:
        player = None

    err_desc = f"{feedback} ({exception})"
    log(f'{player or "Offline user"} sent osu-error: {err_desc}', Ansi.LCYAN)

    # NOTE: this stacktrace can be a LOT of data
    if app.settings.DEBUG and len(stacktrace) < 2000:
        printc(stacktrace[:-2], Ansi.LMAGENTA)

    # TODO: save error in db?

    return Response(b"")


@router.post("/web/osu-screenshot.php")
async def osuScreenshot(
    player: Player = Depends(authenticate_player_session(Form, "u", "p")),
    endpoint_version: int = Form(..., alias="v"),
    screenshot_file: UploadFile = File(..., alias="ss"),  # TODO: why can't i use bytes?
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


@router.get("/web/osu-getfriends.php")
async def osuGetFriends(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
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
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
) -> Response:
    num_requests = len(form_data.Filenames) + len(form_data.Ids)
    log(f"{player} requested info for {num_requests} maps.", Ansi.LCYAN)

    ret = []

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

        ret.append(
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

    return Response("\n".join(ret).encode())


@router.get("/web/osu-getfavourites.php")
async def osuGetFavourites(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
) -> Response:
    rows = await app.state.services.database.fetch_all(
        "SELECT setid FROM favourites WHERE userid = :user_id",
        {"user_id": player.id},
    )

    return Response("\n".join([str(row["setid"]) for row in rows]).encode())


@router.get("/web/osu-addfavourite.php")
async def osuAddFavourite(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    map_set_id: int = Query(..., alias="a"),
) -> Response:
    # check if they already have this favourited.
    if await app.state.services.database.fetch_one(
        "SELECT 1 FROM favourites WHERE userid = :user_id AND setid = :set_id",
        {"user_id": player.id, "set_id": map_set_id},
    ):
        return Response(b"You've already favourited this beatmap!")

    # add favourite
    await app.state.services.database.execute(
        "INSERT INTO favourites VALUES (:user_id, :set_id, UNIX_TIMESTAMP())",
        {"user_id": player.id, "set_id": map_set_id},
    )

    return Response(b"Added favourite!")


#@router.get("/web/lastfm.php")
async def lastFM(
    action: Literal["scrobble", "np"],
    beatmap_id_or_hidden_flag: str = Query(
        ...,
        description=(
            "This flag is normally a beatmap ID, but is also "
            "used as a hidden anticheat flag within osu!"
        ),
        alias="b",
    ),
    player: Player = Depends(authenticate_player_session(Query, "us", "ha")),
) -> Response:
    if beatmap_id_or_hidden_flag[0] != "a":
        # not anticheat related, tell the
        # client not to send any more for now.
        return Response(b"-3")

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
async def osuSearchHandler(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    ranked_status: int = Query(..., alias="r", ge=0, le=8),
    query: str = Query(..., alias="q"),
    mode: int = Query(..., alias="m", ge=-1, le=3),  # -1 for all
    page_num: int = Query(..., alias="p"),
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
async def osuSearchSetHandler(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    map_set_id: int | None = Query(None, alias="s"),
    map_id: int | None = Query(None, alias="b"),
) -> Response:
    # TODO: refactor this to use the new internal bmap(set) api

    # Since we only need set-specific data, we can basically
    # just do same query with either bid or bsid.

    if map_set_id is not None:
        # this is just a normal request
        k, v = ("set_id", map_set_id)
    elif map_id is not None:
        k, v = ("id", map_id)
    else:
        return Response(b"")  # invalid args

    # Get all set data.
    rec = await app.state.services.database.fetch_one(
        "SELECT DISTINCT set_id, artist, "
        "title, status, creator, last_update "
        f"FROM maps WHERE {k} = :v",
        {"v": v},
    )

    if rec is None:
        # TODO: get from osu!
        return Response(b"")

    bmapset = dict(rec._mapping)

    return Response(
        (
            "{set_id}.osz|{artist}|{title}|{creator}|"
            "{status}|10.0|{last_update}|{set_id}|"  # TODO: rating
            "0|0|0|0|0"
        )
        .format(**bmapset)
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
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log(f"Score Data b64: {score_data_b64}", Ansi.LMAGENTA)
        assert isinstance(score_data_b64, str), "Invalid score data"
        replay_file = score_data.getlist("score")[1]
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log(f"Replay File: {replay_file}", Ansi.LMAGENTA)
        assert isinstance(replay_file, StarletteUploadFile), "Invalid replay data"
    except AssertionError as exc:
        # TODO: perhaps better logging?
        log(f"Failed to validate score multipart data: ({exc.args[0]})", Ansi.LRED)
        return None
    else:
        return (
            score_data_b64.encode(),
            replay_file,
        )


def decrypt_score_aes_data(
    # to decode
    score_data_b64: bytes,
    client_hash_b64: bytes,
    # used for decoding
    iv_b64: bytes,
    osu_version: str,
) -> tuple[list[str], str]:
    """Decrypt the base64'ed score data."""
    # TODO: perhaps this should return TypedDict?

    # attempt to decrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_version}".encode(),
        iv=b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    score_data = aes.decrypt(b64decode(score_data_b64)).decode().split(":")
    client_hash_decoded = aes.decrypt(b64decode(client_hash_b64)).decode()

    # score data is delimited by colons (:).
    return score_data, client_hash_decoded

async def get_form_data(type, request: Request):
    try:
        return await request.form()
    except Exception as e:
        # Handle the exception here
        if app.settings.DEBUG and app.settings.DEBUG_REQUESTS:
            log(f"Request has no Form Data", Ansi.GRAY)
        return None

async def get_request_body(type, request: Request):
    try:
        request_body = await request.body()
        log(f"Request Body: {request_body}", Ansi.GRAY, file="./.data/logs/request_bodies.log")
        return request_body
    except Exception as e:
        # Handle the exception here
        if app.settings.DEBUG and app.settings.DEBUG_REQUESTS:
            log(f"Request has no Body", Ansi.GRAY)
        return None

async def get_request_files(type, request: Request):
    try:
        return await request.files()
    except Exception as e:
        # Handle the exception here
        if app.settings.DEBUG and app.settings.DEBUG_REQUESTS:
            log(f"Request Contains no Files", Ansi.GRAY)
        return None


async def write_log_file(type, file_path, request):
    log(f"Writing Log File for Old Client Submission", Ansi.GRAY)
    with open(file_path, 'w') as file:
        if type == "SCORE":
            file.write("Old Client Score Submission:\n")
        file.write(f"Request Headers:\n")
        for header, value in request.headers.items():
            file.write(f"{header}: {value}\n")
        log(f"Request headers written, Grabbing Form_Data Next", Ansi.GRAY)
        form_data = await get_form_data(type, request)
        log(f"Grabbed Form Data", Ansi.GRAY)
        if form_data != None:
            # Extract the aliases and their values from the form data
            aliases = {alias: str(form_data.get(alias)) for alias in form_data}
            # Convert the aliases dictionary to JSON format
            aliases_json = json.dumps(aliases, indent=4)
            file.write("Request Forms: \n")
            file.write(aliases_json)
            log(f"Form Data Written")
        # Read the request body as bytes and decode it
        body = await get_request_body(type, request)
        if body != None:
            try:
                body_str = body.decode()
            except Exception as e:
                body_str = None
            file.write(f"\nRequest Body:\n")
            file.write(body_str)
        files = await get_request_files(type, request)
        if files != None:
            file.write(f"\nFiles:\n")
            for field, uploaded_file in files.items():
                file.write(f"{field}: {uploaded_file.filename}\n")
        if type == "SCORE":
            log(f"Log File for Old Client Submission written successfully", Ansi.GRAY)


if app.settings.CHEAT_SERVER:
    @router.post("/web/osu-submit-modular.php")
    @router.post("/web/osu-submit-modular-selector.php")
    async def osuSubmitModularSelector(
        request: Request,
        # TODO: should token be allowed
        # through but ac'd if not found?
        # TODO: validate token format
        # TODO: save token in the database
        token: str | None = Header(None),
        # TODO: do ft & st contain pauses?
        exited_out: bool | None = Form(None, alias="x"),
        anti_cheat_check: bytes | None = Form(None, alias="pl"),
        fail_time: int | None = Form(None, alias="ft"),
        visual_settings_b64: bytes | None = Form(None, alias="fs"),
        updated_beatmap_hash: str | None = Form(None, alias="bmk"),
        storyboard_md5: str | None = Form(None, alias="sbk"),
        iv_b64: bytes | None = Form(None, alias="iv"),
        unique_ids: str | None = Form(None, alias="c1"),  # TODO: more validaton
        score_time: int | None = Form(None, alias="st"),  # TODO: is this real name?
        pw_md5: str | None = Form(None, alias="pass"),
        osu_version: str | None = Form(None, alias="osuver"),  # TODO: regex
        client_hash_b64: bytes | None = Form(None, alias="s"),
        # TODO: do these need to be Optional?
        # TODO: validate this is actually what it is
        fl_cheat_screenshot: bytes | None = File(None, alias="i"),
        # TODO: Process Cheat Values
        cheat_values: Optional[str] | None = Form(None, alias="cv"),
    ) -> Response:
        """Handle a score submis    sion from an osu! client with an active session."""
            #await get_request_body("SCORE", request)
        if app.settings.DEBUG and app.settings.DEBUG_SCORES and request.url.path == "/web/osu-submit-modular.php":
            log("Received Score Submission from Old Client", Ansi.LMAGENTA)
    
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("Process FL Screenshot", Ansi.LMAGENTA)
        if fl_cheat_screenshot:
            stacktrace = app.utils.get_appropriate_stacktrace()
            await app.state.services.log_strange_occurrence(stacktrace)
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("fl_check Done", Ansi.LMAGENTA)
        # NOTE: the bancho protocol uses the "score" parameter name for both
        # the base64'ed score data, and the replay file in the multipart
        # starlette/fastapi do not support this, so we've moved it out
        score_parameters = parse_form_data_score_params(await request.form())
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("Set Score_Parameters", Ansi.LMAGENTA)
        if score_parameters is None:
            if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                log("Score_Parameters is None", Ansi.LMAGENTA)
            return Response(b"")
    
        # extract the score data and replay file from the score data
        score_data_b64, replay_file = score_parameters
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("handle score parameters", Ansi.LMAGENTA)
        # decrypt the score data (aes)
        score_data, client_hash_decoded = decrypt_score_aes_data(
            score_data_b64,
            client_hash_b64,
            iv_b64,
            osu_version,
        )
    
        # fetch map & player
    
        bmap_md5 = score_data[0]
        bmap = await Beatmap.from_md5(bmap_md5)
        if not bmap:
            # Map does not exist, most likely unsubmitted.
            return Response(b"error: beatmap")
    
        # if the client has supporter, a space is appended
        # but usernames may also end with a space, which must be preserved
        username = score_data[1]
        if username[-1] == " ":
            username = username[:-1]
    
        player = await app.state.sessions.players.from_login(username, pw_md5)
        if not player:
            # Player is not online, return nothing so that their
            # client will retry submission when they log in.
            return Response(b"")
    
        # parse the score from the remaining data
        score = Score.from_submission(score_data[2:])
    
        # attach bmap & player
        score.bmap = bmap
        score.player = player
    
        ## perform checksum validation
    
        unique_id1, unique_id2 = unique_ids.split("|", maxsplit=1)
        unique_id1_md5 = hashlib.md5(unique_id1.encode()).hexdigest()
        unique_id2_md5 = hashlib.md5(unique_id2.encode()).hexdigest()
    
        try:
            assert player.client_details is not None
    
            if osu_version != f"{player.client_details.osu_version.date:%Y%m%d}":
                raise ValueError("osu! version mismatch")
    
            if client_hash_decoded != player.client_details.client_hash:
                raise ValueError("client hash mismatch")
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
            if  (bmap_md5 != None and updated_beatmap_hash != None) and bmap_md5 != updated_beatmap_hash:
                raise ValueError(
                    f"beatmap hash mismatch ({bmap_md5} != {updated_beatmap_hash})",
                )
    
        except (ValueError, AssertionError):
            # NOTE: this is undergoing a temporary trial period,
            # after which, it will be enabled & perform restrictions.
            stacktrace = app.utils.get_appropriate_stacktrace()
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
        score.player.update_latest_activity_soon()
    
        # make sure the player's client displays the correct mode's stats
        if score.mode != score.player.status.mode:
            score.player.status.mods = score.mods
            score.player.status.mode = score.mode
    
            if not score.player.restricted:
                app.state.sessions.players.enqueue(app.packets.user_stats(score.player))
    
        # stop here if this is a duplicate score
        if await app.state.services.database.fetch_one(
            "SELECT 1 FROM scores WHERE online_checksum = :checksum",
            {"checksum": score.client_checksum},
        ):
            log(f"{score.player} submitted a duplicate score.", Ansi.LYELLOW)
            return Response(b"error: no")
    
        # all data read from submission.
        # now we can calculate things based on our data.
        score.acc = score.calculate_accuracy()
    
        if score.bmap:
            osu_file_path = BEATMAPS_PATH / f"{score.bmap.id}.osu"
            if await ensure_local_osu_file(osu_file_path, score.bmap.id, score.bmap.md5):
                score.pp, score.sr = score.calculate_performance(osu_file_path)
    
                if score.passed:
                    await score.calculate_status()
    
                    if score.bmap.status != RankedStatus.Pending:
                        score.rank = await score.calculate_placement()
                else:
                    score.status = SubmissionStatus.FAILED
        else:
            score.pp = score.sr = 0.0
            if score.passed:
                score.status = SubmissionStatus.SUBMITTED
            else:
                score.status = SubmissionStatus.FAILED
    
        if score_time is not None:
                if fail_time is not None:
                    score.time_elapsed = int(score_time) if score.passed else int(fail_time)
        else:
            score.time_elapsed = bmap.total_length
    
        if (  # check for pp caps on ranked & approved maps for appropriate players.
            score.bmap.awards_ranked_pp
            and not (score.player.priv & Privileges.WHITELISTED or score.player.restricted)
        ):
            # Get the PP cap for the current context.
            """# TODO: find where to put autoban pp
            pp_cap = app.settings.AUTOBAN_PP[score.mode][score.mods & Mods.FLASHLIGHT != 0]
    
            if score.pp > pp_cap:
                await score.player.restrict(
                    admin=app.state.sessions.bot,
                    reason=f"[{score.mode!r} {score.mods!r}] autoban @ {score.pp:.2f}pp",
                )
    
                # refresh their client state
                if score.player.online:
                    score.player.logout()
            """
    
        """ Score submission checks completed; submit the score. """
    
        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.submitted_scores")
    
        if score.status == SubmissionStatus.BEST:
            if app.state.services.datadog:
                app.state.services.datadog.increment("bancho.submitted_scores_best")
    
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
    
                score.player.enqueue(
                    app.packets.notification(
                        f"You achieved #{score.rank}! ({performance})",
                    ),
                )
    
                if score.rank == 1 and not score.player.restricted:
                    announce_chan = app.state.sessions.channels.get_by_name("#announce")
    
                    ann = [
                        f"\x01ACTION achieved #1 on {score.bmap.embed}",
                        f"with {score.acc:.2f}% for {performance}.",
                    ]
    
                    if score.mods:
                        ann.insert(1, f"+{score.mods!r}")
    
                    scoring_metric = "pp" if score.mode >= GameMode.RELAX_OSU else "score"
    
                    # If there was previously a score on the map, add old #1.
                    prev_n1 = await app.state.services.database.fetch_one(
                        "SELECT u.id, name FROM users u "
                        "INNER JOIN scores s ON u.id = s.userid "
                        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                        "AND s.status = 2 AND u.priv & 1 "
                        f"ORDER BY s.{scoring_metric} DESC LIMIT 1",
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
    
        if score.passed:
            replay_data = await replay_file.read()
    
            MIN_REPLAY_SIZE = 24
    
            if len(replay_data) >= MIN_REPLAY_SIZE:
                replay_disk_file = REPLAYS_PATH / f"{score.id}.osr"
                replay_disk_file.write_bytes(replay_data)
            else:
                log(f"{score.player} submitted a score without a replay!", Ansi.LRED)
    
                if not score.player.restricted:
                    await score.player.restrict(
                        admin=app.state.sessions.bot,
                        reason="you submitted a score without a replay! what are you trying to pull?",
                    )
                    if score.player.is_online:
                        score.player.logout()
    
        """ Update the user's & beatmap's stats """
    
        # get the current stats, and take a
        # shallow copy for the response charts.
        stats = score.player.gm_stats
        prev_stats = copy.copy(stats)
    
        # stuff update for all submitted scores
        if score.time_elapsed: 
            stats.playtime += score.time_elapsed // 1000
        else:
            stats.playtime += bmap.total_length
        stats.plays += 1
        stats.tscore += score.score
        stats.total_hits += score.n300 + score.n100 + score.n50
    
        if score.mode.as_vanilla in (1, 3):
            # taiko uses geki & katu for hitting big notes with 2 keys
            # mania uses geki & katu for rainbow 300 & 200
            stats.total_hits += score.ngeki + score.nkatu
    
        stats_updates: dict[str, Any] = {
            "plays": stats.plays,
            "playtime": stats.playtime,
            "tscore": stats.tscore,
            "total_hits": stats.total_hits,
        }
    
        if score.passed and score.bmap.has_leaderboard:
            # player passed & map is ranked, approved, or loved.
    
            if score.max_combo > stats.max_combo:
                stats.max_combo = score.max_combo
                stats_updates["max_combo"] = stats.max_combo
    
            if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
                # map is ranked or approved, and it's our (new)
                # best score on the map. update the player's
                # ranked score, grades, pp, acc and global rank.
    
                additional_rscore = score.score
                if score.prev_best:
                    # we previously had a score, so remove
                    # it's score from our ranked score.
                    additional_rscore -= score.prev_best.score
    
                    if score.grade != score.prev_best.grade:
                        if score.grade >= Grade.A:
                            stats.grades[score.grade] += 1
                            grade_col = format(score.grade, "stats_column")
                            stats_updates[grade_col] = stats.grades[score.grade]
    
                        if score.prev_best.grade >= Grade.A:
                            stats.grades[score.prev_best.grade] -= 1
                            grade_col = format(score.prev_best.grade, "stats_column")
                            stats_updates[grade_col] = stats.grades[score.prev_best.grade]
                else:
                    # this is our first submitted score on the map
                    if score.grade >= Grade.A:
                        stats.grades[score.grade] += 1
                        grade_col = format(score.grade, "stats_column")
                        stats_updates[grade_col] = stats.grades[score.grade]
    
                stats.rscore += additional_rscore
                stats_updates["rscore"] = stats.rscore
    
                # fetch scores sorted by pp for total acc/pp calc
                # NOTE: we select all plays (and not just top100)
                # because bonus pp counts the total amount of ranked
                # scores. I'm aware this scales horribly, and it'll
                # likely be split into two queries in the future.
                best_scores = await app.state.services.database.fetch_all(
                    "SELECT s.pp, s.acc FROM scores s "
                    "INNER JOIN maps m ON s.map_md5 = m.md5 "
                    "WHERE s.userid = :user_id AND s.mode = :mode "
                    "AND s.status = 2 AND m.status IN (2, 3) "  # ranked, approved
                    "ORDER BY s.pp DESC",
                    {"user_id": score.player.id, "mode": score.mode},
                )
    
                # calculate new total weighted accuracy
                weighted_acc = sum(
                    row["acc"] * 0.95**i for i, row in enumerate(best_scores)
                )
                bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(best_scores)))
                stats.acc = (weighted_acc * bonus_acc) / 100
                stats_updates["acc"] = stats.acc
    
                # calculate new total weighted pp
                weighted_pp = sum(
                    row["pp"] * 0.95**i for i, row in enumerate(best_scores)
                )
                bonus_pp = 416.6667 * (1 - 0.9994 ** len(best_scores))
                stats.pp = round(weighted_pp + bonus_pp)
                stats_updates["pp"] = stats.pp
    
                # update global & country ranking
                stats.rank = await score.player.update_rank(score.mode)
    
        await stats_repo.update(
            score.player.id,
            score.mode.value,
            plays=stats_updates.get("plays", UNSET),
            playtime=stats_updates.get("playtime", UNSET),
            tscore=stats_updates.get("tscore", UNSET),
            total_hits=stats_updates.get("total_hits", UNSET),
            max_combo=stats_updates.get("max_combo", UNSET),
            xh_count=stats_updates.get("xh_count", UNSET),
            x_count=stats_updates.get("x_count", UNSET),
            sh_count=stats_updates.get("sh_count", UNSET),
            s_count=stats_updates.get("s_count", UNSET),
            a_count=stats_updates.get("a_count", UNSET),
            rscore=stats_updates.get("rscore", UNSET),
            acc=stats_updates.get("acc", UNSET),
            pp=stats_updates.get("pp", UNSET),
        )
    
        if not score.player.restricted:
            # enqueue new stats info to all other users
            app.state.sessions.players.enqueue(app.packets.user_stats(score.player))
    
            # update beatmap with new stats
            score.bmap.plays += 1
            if score.passed:
                score.bmap.passes += 1
    
            await app.state.services.database.execute(
                "UPDATE maps SET plays = :plays, passes = :passes WHERE md5 = :map_md5",
                {
                    "plays": score.bmap.plays,
                    "passes": score.bmap.passes,
                    "map_md5": score.bmap.md5,
                },
            )
    
        # update their recent score
        score.player.recent_scores[score.mode] = score
    
        """ score submission charts """
    
        # charts are only displayed for passes vanilla gamemodes.
        if not score.passed or score.mode not in (
            GameMode.VANILLA_OSU,
            GameMode.VANILLA_TAIKO,
            GameMode.VANILLA_CATCH,
            GameMode.VANILLA_MANIA,
        ):
            response = b"error: no"
        else:
            # construct and send achievements & ranking charts to the client
            if score.bmap.awards_ranked_pp and not score.player.restricted:
                unlocked_achievements: list[Achievement] = []
    
                server_achievements = await achievements_usecases.fetch_many()
                player_achievements = await user_achievements_usecases.fetch_many(
                    score.player.id,
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
                        await user_achievements_usecases.create(
                            score.player.id,
                            server_achievement["id"],
                        )
                        unlocked_achievements.append(server_achievement)
    
                achievements_str = "/".join(
                    format_achievement_string(a["file"], a["name"], a["desc"])
                    for a in unlocked_achievements
                )
            else:
                achievements_str = ""
    
            # create score submission charts for osu! client to display
    
            if score.prev_best:
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
                beatmap_ranking_chart_entries = (
                    chart_entry("rank", None, score.rank),
                    chart_entry("rankedScore", None, score.score),
                    chart_entry("totalScore", None, score.score),
                    chart_entry("maxCombo", None, score.max_combo),
                    chart_entry("accuracy", None, round(score.acc, 2)),
                    chart_entry("pp", None, score.pp),
                )
    
            overall_ranking_chart_entries = (
                chart_entry("rank", prev_stats.rank, stats.rank),
                chart_entry("rankedScore", prev_stats.rscore, stats.rscore),
                chart_entry("totalScore", prev_stats.tscore, stats.tscore),
                chart_entry("maxCombo", prev_stats.max_combo, stats.max_combo),
                chart_entry("accuracy", round(prev_stats.acc, 2), round(stats.acc, 2)),
                chart_entry("pp", prev_stats.pp, stats.pp),
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
        if app.settings.CHEAT_SERVER:
            if cheat_values:
                if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                    log(f"Cheat Values: {cheat_values}", Ansi.GRAY, file="./.data/logs/cheat_values.log")
                cheat_values_str = json.dumps(cheat_values)
                if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                    log(f"Score ID: {score.id}, Score Status: {score.status}")
                if (score.status == 2) or (score.status > 0 and score.id and score.id != 0):
                    if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                        log(f"Score ID: {score.id}")
                    await app.state.services.database.execute(
                        "INSERT INTO scoreinfo (scoreid, cheat_values) "
                        "VALUES (:scoreid, :cheat_values)",
                        {
                            "scoreid": score.id,
                            "cheat_values": cheat_values_str,
                        },
                    )
        log(
            f"[{score.mode!r}] {score.player} submitted a score! "
            f"({score.status!r}, {score.pp:,.2f}pp / {stats.pp:,}pp)",
            Ansi.LGREEN,
        )
        # TODO: execute write log in a way that is non blocking
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            ocsslc = app.settings.OLD_CLIENT_SCORE_SUBMIT_LOG_COUNT
            app.settings.OLD_CLIENT_SCORE_SUBMIT_LOG_COUNT = ocsslc + 1
            if request.url.path == "/web/osu-submit-modular.php":
                clientfolder = "oldclients"
            else:
                clientfolder = "newclients"
            file_path = f"./.data/logs/scores/{clientfolder}/submission{ocsslc}.log"
    
            # Create the file if it doesn't exist
            if not os.path.exists(file_path):
                open(file_path, 'a').close()
    
            # Execute Write Log
            asyncio.create_task(write_log_file("SCORE", file_path, request))
        return Response(response)
else:
    @router.post("/web/osu-submit-modular-selector.php")
    async def osuSubmitModularSelector(
        request: Request,
        # TODO: should token be allowed
        # through but ac'd if not found?
        # TODO: validate token format
        # TODO: save token in the database
        token: str | None = Header(None),
        # TODO: do ft & st contain pauses?
        exited_out: bool | None = Form(None, alias="x"),
        anti_cheat_check: bytes | None = Form(None, alias="pl"),
        fail_time: int | None = Form(None, alias="ft"),
        visual_settings_b64: bytes | None = Form(None, alias="fs"),
        updated_beatmap_hash: str | None = Form(None, alias="bmk"),
        storyboard_md5: str | None = Form(None, alias="sbk"),
        iv_b64: bytes | None = Form(None, alias="iv"),
        unique_ids: str | None = Form(None, alias="c1"),  # TODO: more validaton
        score_time: int | None = Form(None, alias="st"),  # TODO: is this real name?
        pw_md5: str | None = Form(None, alias="pass"),
        osu_version: str | None = Form(None, alias="osuver"),  # TODO: regex
        client_hash_b64: bytes | None = Form(None, alias="s"),
        # TODO: do these need to be Optional?
        # TODO: validate this is actually what it is
        fl_cheat_screenshot: bytes | None = File(None, alias="i"),
        # TODO: Process Cheat Values
        cheat_values: Optional[str] | None = Form(None, alias="cv"),
    ) -> Response:
        """Handle a score submis    sion from an osu! client with an active session."""
            #await get_request_body("SCORE", request)
        if app.settings.DEBUG and app.settings.DEBUG_SCORES and request.url.path == "/web/osu-submit-modular.php":
            log("Received Score Submission from Old Client", Ansi.LMAGENTA)
    
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("Process FL Screenshot", Ansi.LMAGENTA)
        if fl_cheat_screenshot:
            stacktrace = app.utils.get_appropriate_stacktrace()
            await app.state.services.log_strange_occurrence(stacktrace)
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("fl_check Done", Ansi.LMAGENTA)
        # NOTE: the bancho protocol uses the "score" parameter name for both
        # the base64'ed score data, and the replay file in the multipart
        # starlette/fastapi do not support this, so we've moved it out
        score_parameters = parse_form_data_score_params(await request.form())
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("Set Score_Parameters", Ansi.LMAGENTA)
        if score_parameters is None:
            if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                log("Score_Parameters is None", Ansi.LMAGENTA)
            return Response(b"")
    
        # extract the score data and replay file from the score data
        score_data_b64, replay_file = score_parameters
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            log("handle score parameters", Ansi.LMAGENTA)
        # decrypt the score data (aes)
        score_data, client_hash_decoded = decrypt_score_aes_data(
            score_data_b64,
            client_hash_b64,
            iv_b64,
            osu_version,
        )
    
        # fetch map & player
    
        bmap_md5 = score_data[0]
        bmap = await Beatmap.from_md5(bmap_md5)
        if not bmap:
            # Map does not exist, most likely unsubmitted.
            return Response(b"error: beatmap")
    
        # if the client has supporter, a space is appended
        # but usernames may also end with a space, which must be preserved
        username = score_data[1]
        if username[-1] == " ":
            username = username[:-1]
    
        player = await app.state.sessions.players.from_login(username, pw_md5)
        if not player:
            # Player is not online, return nothing so that their
            # client will retry submission when they log in.
            return Response(b"")
    
        # parse the score from the remaining data
        score = Score.from_submission(score_data[2:])
    
        # attach bmap & player
        score.bmap = bmap
        score.player = player
    
        ## perform checksum validation
    
        unique_id1, unique_id2 = unique_ids.split("|", maxsplit=1)
        unique_id1_md5 = hashlib.md5(unique_id1.encode()).hexdigest()
        unique_id2_md5 = hashlib.md5(unique_id2.encode()).hexdigest()
    
        try:
            assert player.client_details is not None
    
            if osu_version != f"{player.client_details.osu_version.date:%Y%m%d}":
                raise ValueError("osu! version mismatch")
    
            if client_hash_decoded != player.client_details.client_hash:
                raise ValueError("client hash mismatch")
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
            if  (bmap_md5 != None and updated_beatmap_hash != None) and bmap_md5 != updated_beatmap_hash:
                raise ValueError(
                    f"beatmap hash mismatch ({bmap_md5} != {updated_beatmap_hash})",
                )
    
        except (ValueError, AssertionError):
            # NOTE: this is undergoing a temporary trial period,
            # after which, it will be enabled & perform restrictions.
            stacktrace = app.utils.get_appropriate_stacktrace()
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
        score.player.update_latest_activity_soon()
    
        # make sure the player's client displays the correct mode's stats
        if score.mode != score.player.status.mode:
            score.player.status.mods = score.mods
            score.player.status.mode = score.mode
    
            if not score.player.restricted:
                app.state.sessions.players.enqueue(app.packets.user_stats(score.player))
    
        # stop here if this is a duplicate score
        if await app.state.services.database.fetch_one(
            "SELECT 1 FROM scores WHERE online_checksum = :checksum",
            {"checksum": score.client_checksum},
        ):
            log(f"{score.player} submitted a duplicate score.", Ansi.LYELLOW)
            return Response(b"error: no")
    
        # all data read from submission.
        # now we can calculate things based on our data.
        score.acc = score.calculate_accuracy()
    
        if score.bmap:
            osu_file_path = BEATMAPS_PATH / f"{score.bmap.id}.osu"
            if await ensure_local_osu_file(osu_file_path, score.bmap.id, score.bmap.md5):
                score.pp, score.sr = score.calculate_performance(osu_file_path)
    
                if score.passed:
                    await score.calculate_status()
    
                    if score.bmap.status != RankedStatus.Pending:
                        score.rank = await score.calculate_placement()
                else:
                    score.status = SubmissionStatus.FAILED
        else:
            score.pp = score.sr = 0.0
            if score.passed:
                score.status = SubmissionStatus.SUBMITTED
            else:
                score.status = SubmissionStatus.FAILED
    
        if score_time is not None:
                if fail_time is not None:
                    score.time_elapsed = int(score_time) if score.passed else int(fail_time)
        else:
            score.time_elapsed = bmap.total_length
    
        if (  # check for pp caps on ranked & approved maps for appropriate players.
            score.bmap.awards_ranked_pp
            and not (score.player.priv & Privileges.WHITELISTED or score.player.restricted)
        ):
            # Get the PP cap for the current context.
            """# TODO: find where to put autoban pp
            pp_cap = app.settings.AUTOBAN_PP[score.mode][score.mods & Mods.FLASHLIGHT != 0]
    
            if score.pp > pp_cap:
                await score.player.restrict(
                    admin=app.state.sessions.bot,
                    reason=f"[{score.mode!r} {score.mods!r}] autoban @ {score.pp:.2f}pp",
                )
    
                # refresh their client state
                if score.player.online:
                    score.player.logout()
            """
    
        """ Score submission checks completed; submit the score. """
    
        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.submitted_scores")
    
        if score.status == SubmissionStatus.BEST:
            if app.state.services.datadog:
                app.state.services.datadog.increment("bancho.submitted_scores_best")
    
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
    
                score.player.enqueue(
                    app.packets.notification(
                        f"You achieved #{score.rank}! ({performance})",
                    ),
                )
    
                if score.rank == 1 and not score.player.restricted:
                    announce_chan = app.state.sessions.channels.get_by_name("#announce")
    
                    ann = [
                        f"\x01ACTION achieved #1 on {score.bmap.embed}",
                        f"with {score.acc:.2f}% for {performance}.",
                    ]
    
                    if score.mods:
                        ann.insert(1, f"+{score.mods!r}")
    
                    scoring_metric = "pp" if score.mode >= GameMode.RELAX_OSU else "score"
    
                    # If there was previously a score on the map, add old #1.
                    prev_n1 = await app.state.services.database.fetch_one(
                        "SELECT u.id, name FROM users u "
                        "INNER JOIN scores s ON u.id = s.userid "
                        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                        "AND s.status = 2 AND u.priv & 1 "
                        f"ORDER BY s.{scoring_metric} DESC LIMIT 1",
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
    
        if score.passed:
            replay_data = await replay_file.read()
    
            MIN_REPLAY_SIZE = 24
    
            if len(replay_data) >= MIN_REPLAY_SIZE:
                replay_disk_file = REPLAYS_PATH / f"{score.id}.osr"
                replay_disk_file.write_bytes(replay_data)
            else:
                log(f"{score.player} submitted a score without a replay!", Ansi.LRED)
    
                if not score.player.restricted:
                    await score.player.restrict(
                        admin=app.state.sessions.bot,
                        reason="you submitted a score without a replay! what are you trying to pull?",
                    )
                    if score.player.is_online:
                        score.player.logout()
    
        """ Update the user's & beatmap's stats """
    
        # get the current stats, and take a
        # shallow copy for the response charts.
        stats = score.player.gm_stats
        prev_stats = copy.copy(stats)
    
        # stuff update for all submitted scores
        if score.time_elapsed: 
            stats.playtime += score.time_elapsed // 1000
        else:
            stats.playtime += bmap.total_length
        stats.plays += 1
        stats.tscore += score.score
        stats.total_hits += score.n300 + score.n100 + score.n50
    
        if score.mode.as_vanilla in (1, 3):
            # taiko uses geki & katu for hitting big notes with 2 keys
            # mania uses geki & katu for rainbow 300 & 200
            stats.total_hits += score.ngeki + score.nkatu
    
        stats_updates: dict[str, Any] = {
            "plays": stats.plays,
            "playtime": stats.playtime,
            "tscore": stats.tscore,
            "total_hits": stats.total_hits,
        }
    
        if score.passed and score.bmap.has_leaderboard:
            # player passed & map is ranked, approved, or loved.
    
            if score.max_combo > stats.max_combo:
                stats.max_combo = score.max_combo
                stats_updates["max_combo"] = stats.max_combo
    
            if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
                # map is ranked or approved, and it's our (new)
                # best score on the map. update the player's
                # ranked score, grades, pp, acc and global rank.
    
                additional_rscore = score.score
                if score.prev_best:
                    # we previously had a score, so remove
                    # it's score from our ranked score.
                    additional_rscore -= score.prev_best.score
    
                    if score.grade != score.prev_best.grade:
                        if score.grade >= Grade.A:
                            stats.grades[score.grade] += 1
                            grade_col = format(score.grade, "stats_column")
                            stats_updates[grade_col] = stats.grades[score.grade]
    
                        if score.prev_best.grade >= Grade.A:
                            stats.grades[score.prev_best.grade] -= 1
                            grade_col = format(score.prev_best.grade, "stats_column")
                            stats_updates[grade_col] = stats.grades[score.prev_best.grade]
                else:
                    # this is our first submitted score on the map
                    if score.grade >= Grade.A:
                        stats.grades[score.grade] += 1
                        grade_col = format(score.grade, "stats_column")
                        stats_updates[grade_col] = stats.grades[score.grade]
    
                stats.rscore += additional_rscore
                stats_updates["rscore"] = stats.rscore
    
                # fetch scores sorted by pp for total acc/pp calc
                # NOTE: we select all plays (and not just top100)
                # because bonus pp counts the total amount of ranked
                # scores. I'm aware this scales horribly, and it'll
                # likely be split into two queries in the future.
                best_scores = await app.state.services.database.fetch_all(
                    "SELECT s.pp, s.acc FROM scores s "
                    "INNER JOIN maps m ON s.map_md5 = m.md5 "
                    "WHERE s.userid = :user_id AND s.mode = :mode "
                    "AND s.status = 2 AND m.status IN (2, 3) "  # ranked, approved
                    "ORDER BY s.pp DESC",
                    {"user_id": score.player.id, "mode": score.mode},
                )
    
                # calculate new total weighted accuracy
                weighted_acc = sum(
                    row["acc"] * 0.95**i for i, row in enumerate(best_scores)
                )
                bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(best_scores)))
                stats.acc = (weighted_acc * bonus_acc) / 100
                stats_updates["acc"] = stats.acc
    
                # calculate new total weighted pp
                weighted_pp = sum(
                    row["pp"] * 0.95**i for i, row in enumerate(best_scores)
                )
                bonus_pp = 416.6667 * (1 - 0.9994 ** len(best_scores))
                stats.pp = round(weighted_pp + bonus_pp)
                stats_updates["pp"] = stats.pp
    
                # update global & country ranking
                stats.rank = await score.player.update_rank(score.mode)
    
        await stats_repo.update(
            score.player.id,
            score.mode.value,
            plays=stats_updates.get("plays", UNSET),
            playtime=stats_updates.get("playtime", UNSET),
            tscore=stats_updates.get("tscore", UNSET),
            total_hits=stats_updates.get("total_hits", UNSET),
            max_combo=stats_updates.get("max_combo", UNSET),
            xh_count=stats_updates.get("xh_count", UNSET),
            x_count=stats_updates.get("x_count", UNSET),
            sh_count=stats_updates.get("sh_count", UNSET),
            s_count=stats_updates.get("s_count", UNSET),
            a_count=stats_updates.get("a_count", UNSET),
            rscore=stats_updates.get("rscore", UNSET),
            acc=stats_updates.get("acc", UNSET),
            pp=stats_updates.get("pp", UNSET),
        )
    
        if not score.player.restricted:
            # enqueue new stats info to all other users
            app.state.sessions.players.enqueue(app.packets.user_stats(score.player))
    
            # update beatmap with new stats
            score.bmap.plays += 1
            if score.passed:
                score.bmap.passes += 1
    
            await app.state.services.database.execute(
                "UPDATE maps SET plays = :plays, passes = :passes WHERE md5 = :map_md5",
                {
                    "plays": score.bmap.plays,
                    "passes": score.bmap.passes,
                    "map_md5": score.bmap.md5,
                },
            )
    
        # update their recent score
        score.player.recent_scores[score.mode] = score
    
        """ score submission charts """
    
        # charts are only displayed for passes vanilla gamemodes.
        if not score.passed or score.mode not in (
            GameMode.VANILLA_OSU,
            GameMode.VANILLA_TAIKO,
            GameMode.VANILLA_CATCH,
            GameMode.VANILLA_MANIA,
        ):
            response = b"error: no"
        else:
            # construct and send achievements & ranking charts to the client
            if score.bmap.awards_ranked_pp and not score.player.restricted:
                unlocked_achievements: list[Achievement] = []
    
                server_achievements = await achievements_usecases.fetch_many()
                player_achievements = await user_achievements_usecases.fetch_many(
                    score.player.id,
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
                        await user_achievements_usecases.create(
                            score.player.id,
                            server_achievement["id"],
                        )
                        unlocked_achievements.append(server_achievement)
    
                achievements_str = "/".join(
                    format_achievement_string(a["file"], a["name"], a["desc"])
                    for a in unlocked_achievements
                )
            else:
                achievements_str = ""
    
            # create score submission charts for osu! client to display
    
            if score.prev_best:
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
                beatmap_ranking_chart_entries = (
                    chart_entry("rank", None, score.rank),
                    chart_entry("rankedScore", None, score.score),
                    chart_entry("totalScore", None, score.score),
                    chart_entry("maxCombo", None, score.max_combo),
                    chart_entry("accuracy", None, round(score.acc, 2)),
                    chart_entry("pp", None, score.pp),
                )
    
            overall_ranking_chart_entries = (
                chart_entry("rank", prev_stats.rank, stats.rank),
                chart_entry("rankedScore", prev_stats.rscore, stats.rscore),
                chart_entry("totalScore", prev_stats.tscore, stats.tscore),
                chart_entry("maxCombo", prev_stats.max_combo, stats.max_combo),
                chart_entry("accuracy", round(prev_stats.acc, 2), round(stats.acc, 2)),
                chart_entry("pp", prev_stats.pp, stats.pp),
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
        if app.settings.CHEAT_SERVER:
            if cheat_values:
                if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                    log(f"Cheat Values: {cheat_values}", Ansi.GRAY, file="./.data/logs/cheat_values.log")
                cheat_values_str = json.dumps(cheat_values)
                if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                    log(f"Score ID: {score.id}, Score Status: {score.status}")
                if (score.status == 2) or (score.status > 0 and score.id and score.id != 0):
                    if app.settings.DEBUG and app.settings.DEBUG_SCORES:
                        log(f"Score ID: {score.id}")
                    await app.state.services.database.execute(
                        "INSERT INTO scoreinfo (scoreid, cheat_values) "
                        "VALUES (:scoreid, :cheat_values)",
                        {
                            "scoreid": score.id,
                            "cheat_values": cheat_values_str,
                        },
                    )
        log(
            f"[{score.mode!r}] {score.player} submitted a score! "
            f"({score.status!r}, {score.pp:,.2f}pp / {stats.pp:,}pp)",
            Ansi.LGREEN,
        )
        # TODO: execute write log in a way that is non blocking
        if app.settings.DEBUG and app.settings.DEBUG_SCORES:
            ocsslc = app.settings.OLD_CLIENT_SCORE_SUBMIT_LOG_COUNT
            app.settings.OLD_CLIENT_SCORE_SUBMIT_LOG_COUNT = ocsslc + 1
            if request.url.path == "/web/osu-submit-modular.php":
                clientfolder = "oldclients"
            else:
                clientfolder = "newclients"
            file_path = f"./.data/logs/scores/{clientfolder}/submission{ocsslc}.log"
    
            # Create the file if it doesn't exist
            if not os.path.exists(file_path):
                open(file_path, 'a').close()
    
            # Execute Write Log
            asyncio.create_task(write_log_file("SCORE", file_path, request))
        return Response(response)


@router.get("/web/osu-getreplay.php")
async def getReplay(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    mode: int = Query(..., alias="m", ge=0, le=3),
    score_id: int = Query(..., alias="c", min=0, max=9_223_372_036_854_775_807),
) -> Response:
    score = await Score.from_sql(score_id)
    if not score:
        return Response(b"", status_code=404)

    file = REPLAYS_PATH / f"{score_id}.osr"
    if not file.exists():
        return Response(b"", status_code=404)

    # increment replay views for this score
    if score.player is not None and player.id != score.player.id:
        app.state.loop.create_task(score.increment_replay_views())

    return FileResponse(file)


@router.get("/web/osu-rate.php")
async def osuRate(
    player: Player = Depends(
        authenticate_player_session(Query, "u", "p", err=b"auth fail"),
    ),
    map_md5: str = Query(..., alias="c", max_length=32),
    rating: int | None = Query(None, alias="v", ge=1, le=10),
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
        has_previous_rating = (
            await app.state.services.database.fetch_one(
                "SELECT 1 FROM ratings WHERE map_md5 = :map_md5 AND userid = :user_id",
                {"map_md5": map_md5, "user_id": player.id},
            )
            is not None
        )

        # the client hasn't rated the map, so simply
        # tell them that they can submit a rating.
        if not has_previous_rating:
            return Response(b"ok")
    else:
        # the client is submitting a rating for the map.
        await app.state.services.database.execute(
            "INSERT INTO ratings VALUES (:user_id, :map_md5, :rating)",
            {"user_id": player.id, "map_md5": map_md5, "rating": int(rating)},
        )

    ratings = [
        row[0]
        for row in await app.state.services.database.fetch_all(
            "SELECT rating FROM ratings WHERE map_md5 = :map_md5",
            {"map_md5": map_md5},
        )
    ]

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
    query = [
        f"SELECT s.id, s.{scoring_metric} AS _score, "
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

    score_rows = [
        dict(r._mapping)
        for r in await app.state.services.database.fetch_all(
            " ".join(query),
            params,
        )
    ]

    if score_rows:  # None or []
        # fetch player's personal best score
        personal_best_score_rec = await app.state.services.database.fetch_one(
            f"SELECT id, {scoring_metric} AS _score, "
            "max_combo, n50, n100, n300, "
            "nmiss, nkatu, ngeki, perfect, mods, "
            "UNIX_TIMESTAMP(play_time) time "
            "FROM scores "
            "WHERE map_md5 = :map_md5 AND mode = :mode "
            "AND userid = :user_id AND status = 2 "
            "ORDER BY _score DESC LIMIT 1",
            {"map_md5": map_md5, "mode": mode, "user_id": player.id},
        )

        if personal_best_score_rec is not None:
            personal_best_score_row = dict(personal_best_score_rec._mapping)

            # calculate the rank of the score.
            p_best_rank = 1 + await app.state.services.database.fetch_val(
                "SELECT COUNT(*) FROM scores s "
                "INNER JOIN users u ON u.id = s.userid "
                "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                "AND s.status = 2 AND u.priv & 1 "
                f"AND s.{scoring_metric} > :score",
                {
                    "map_md5": map_md5,
                    "mode": mode,
                    "score": personal_best_score_row["_score"],
                },
                column=0,  # COUNT(*)
            )

            # attach rank to personal best row
            personal_best_score_row["rank"] = p_best_rank
        else:
            personal_best_score_row = None
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
async def getScores(
    player: Player = Depends(authenticate_player_session(Query, "us", "ha")),
    requesting_from_editor_song_select: bool = Query(..., alias="s"),
    leaderboard_version: int = Query(..., alias="vv"),
    leaderboard_type: int = Query(..., alias="v", ge=0, le=4),
    map_md5: str = Query(..., alias="c", min_length=32, max_length=32),
    map_filename: str = Query(..., alias="f"),  # TODO: regex?
    mode_arg: int = Query(..., alias="m", ge=0, le=3),
    map_set_id: int = Query(..., alias="i", ge=-1, le=2_147_483_647),
    mods_arg: int = Query(..., alias="mods", ge=0, le=2_147_483_647),
    map_package_hash: str = Query(..., alias="h"),  # TODO: further validation
    aqn_files_found: bool = Query(..., alias="a"),
) -> Response:
    if app.settings.DEBUG and app.settings.DEBUG_LEADERBOARDS:
        log(f"Player: {player} \n Requesting from editor: {requesting_from_editor_song_select} \n Leaderboard version: {leaderboard_version} \n Leaderboard type: {leaderboard_type} \n Map md5: {map_md5} \n Map filename: {map_filename} \n Mode arg: {mode_arg} \n Map set id: {map_set_id} \n Mods arg: {mods_arg} \n Map package hash: {map_package_hash} \n AQN files found: {aqn_files_found}", Ansi.LMAGENTA)
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
        app.state.services.datadog.increment("bancho.leaderboards_served")

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
    rating = await bmap.fetch_rating()
    if rating is None:
        rating = 0.0

    ## construct response for osu! client

    response_lines: list[str] = [
        # NOTE: fa stands for featured artist (for the ones that may not know)
        # {ranked_status}|{serv_has_osz2}|{bid}|{bsid}|{len(scores)}|{fa_track_id}|{fa_license_text}
        f"{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{len(score_rows)}|0|",
        # {offset}\n{beatmap_name}\n{rating}
        # TODO: server side beatmap offsets
        f"0\n{bmap.full_name}\n{rating}",
    ]

    if not score_rows:
        response_lines.extend(("", ""))  # no scores, no personal best
        return Response("\n".join(response_lines).encode())

    if personal_best_score_row is not None:
        response_lines.append(
            SCORE_LISTING_FMTSTR.format(
                **personal_best_score_row,
                name=player.full_name,
                userid=player.id,
                score=int(personal_best_score_row["_score"]),
                has_replay="1",
            ),
        )
    else:
        response_lines.append("")

    response_lines.extend(
        [
            SCORE_LISTING_FMTSTR.format(
                **s,
                score=int(s["_score"]),
                has_replay="1",
                rank=idx + 1,
            )
            for idx, s in enumerate(score_rows)
        ],
    )

    return Response("\n".join(response_lines).encode())

# TODO: Fix Consuming Bytes on old Client | Disabled for now | Somehow consume request body before server consumes it on it own?
#@router.post("/web/osu-comment.php")
async def osuComment(
    player: Player = Depends(authenticate_player_session(Form, "u", "p")),
    map_id: int = Form(..., alias="b"),
    map_set_id: int = Form(..., alias="s"),
    score_id: int = Form(..., alias="r", ge=0, le=9_223_372_036_854_775_807),
    mode_vn: int = Form(..., alias="m", ge=0, le=3),
    action: Literal["get", "post"] = Form(..., alias="a"),
    # only sent for post
    target: Literal["song", "map", "replay"] | None = Form(None),
    colour: str | None = Form(None, alias="f", min_length=6, max_length=6),
    start_time: int | None = Form(None, alias="starttime"),
    comment: str | None = Form(None, min_length=1, max_length=80),
) -> Response:
    if action == "get":
        # client is requesting all comments
        comments = [
            dict(c._mapping)
            for c in await app.state.services.database.fetch_all(
                "SELECT c.time, c.target_type, c.colour, "
                "c.comment, u.priv FROM comments c "
                "INNER JOIN users u ON u.id = c.userid "
                "WHERE (c.target_type = 'replay' AND c.target_id = :score_id) "
                "OR (c.target_type = 'song' AND c.target_id = :set_id) "
                "OR (c.target_type = 'map' AND c.target_id = :map_id) ",
                {
                    "score_id": score_id,
                    "set_id": map_set_id,
                    "map_id": map_id,
                },
            )
        ]

        ret: list[str] = []

        for cmt in comments:
            # TODO: maybe support player/creator colours?
            # pretty expensive for very low gain, but completion :D
            if cmt["priv"] & Privileges.NOMINATOR:
                fmt = "bat"
            elif cmt["priv"] & Privileges.DONATOR:
                fmt = "supporter"
            else:
                fmt = ""

            if cmt["colour"]:
                fmt += f'|{cmt["colour"]}'

            ret.append(
                "{time}\t{target_type}\t{fmt}\t{comment}".format(fmt=fmt, **cmt),
            )

        player.update_latest_activity_soon()
        return Response("\n".join(ret).encode())

    elif action == "post":
        # client is submitting a new comment
        # TODO: maybe validate all params are sent?

        # get the corresponding id from the request
        if target == "song":
            target_id = map_set_id
        elif target == "map":
            target_id = map_id
        else:  # target == "replay"
            target_id = score_id

        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            # TODO: should we be restricting them?
            colour = None

        # insert into sql
        await app.state.services.database.execute(
            "INSERT INTO comments "
            "(target_id, target_type, userid, time, comment, colour) "
            "VALUES (:target_id, :target_type, :userid, :time, :comment, :colour)",
            {
                "target_id": target_id,
                "target_type": target,
                "userid": player.id,
                "time": start_time,
                "comment": comment,
                "colour": colour,
            },
        )

        player.update_latest_activity_soon()

    return Response(b"")  # empty resp is fine


@router.get("/web/osu-markasread.php") # TODO: Implement into Kawata Client | Fix Unread Message Spam | Add a check for client not supporting this??? | Search `read` = 0 for other half.
async def osuMarkAsRead(
    player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    channel: str = Query(..., min_length=0, max_length=32),
) -> Response:
    target_name = unquote(channel)  # TODO: unquote needed?
    if not target_name:
        return Response(b"")  # no channel specified

    target = await app.state.sessions.players.from_cache_or_sql(name=target_name)
    if target:
        # mark any unread mail from this user as read.
        await app.state.services.database.execute(
            "UPDATE `mail` SET `read` = 1 "
            "WHERE `to_id` = :to AND `from_id` = :from "
            "AND `read` = 0",
            {"to": player.id, "from": target.id},
        )

    return Response(b"")


@router.get("/web/osu-getseasonal.php")
async def osuSeasonal() -> Response:
    return ORJSONResponse(app.settings.SEASONAL_BGS)


#@router.get("/web/bancho_connect.php")
async def banchoConnect(
    # NOTE: this is disabled as this endpoint can be called
    #       before a player has been granted a session
    # player: Player = Depends(authenticate_player_session(Query, "u", "h")),
    osu_ver: str = Query(..., alias="v"),
    active_endpoint: str | None = Query(None, alias="fail"),
    net_framework_vers: str | None = Query(None, alias="fx"),  # delimited by |
    client_hash: str | None = Query(None, alias="ch"),
    retrying: bool | None = Query(None, alias="retry"),  # '0' or '1'
) -> Response:
    return Response(b"")  # TODO


_checkupdates_cache = {  # default timeout is 1h, set on request.
    "cuttingedge": {"check": None, "path": None, "timeout": 0},
    "stable40": {"check": None, "path": None, "timeout": 0},
    "beta40": {"check": None, "path": None, "timeout": 0},
    "stable": {"check": None, "path": None, "timeout": 0},
}


@router.get("/web/check-updates.php")
async def checkUpdates(
    request: Request,
    action: Literal["check", "path", "error"],
    stream: Literal["cuttingedge", "stable40", "beta40", "stable"],
) -> Response:
    return Response(b"")


@router.get("/web/check-aeris-updates.php")
async def checkAerisUpdates(
    request: Request,
    action: Literal["check", "path", "error"],
    stream: Literal["cuttingedge", "stable40", "beta40", "stable"],
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
		"osu!common.dll", #
		"osu!gameplay.dll", #
		"osu!ui.dll", 
		"osu!.exe", 
		"osu.dll", #
		"pthreadGC2.dll",
		"SmartThreadPool.dll", #
        "WindowsInput.dll"
	]
    args = {}

    for key, _ in request.query_params.items():
        args[key] = request.query_params[key].lower()

    if args["action"].lower() == "put":
        return Response(b"nope")

    if args["stream"].lower() == "cuttingedge":
        args["stream"] = "stable40"

    if args["stream"].lower() == "stable":
        neededFiles.append("oppai.exe")

    if args["stream"].lower() == "stable40":
        neededFiles.append("DiscordRPC.dll")
    
    if args["action"].lower() == "check" or args["action"].lower() == "path":
        try:
            updaterCache = ".data/storage/updater/{}/{}".format(args["stream"], "updater.json")
            if not os.path.exists(updaterCache):
                needUpdate = True
            result = []
            log("[Aeris updater]: requested Update for : {}".format(args["stream"]))
            try:
                data = json.loads(open(updaterCache, "r").read())
                needUpdate = len(data) < len(neededFiles)
                index = 0
                if not needUpdate:
                    for x in neededFiles:
                        timestamp = time.strftime('%m-%d-%Y %H:%M:%S', time.gmtime(os.path.getmtime(".data/storage/updater/{}/{}".format(args["stream"], x))))

                        if data[index]["timestamp"] != timestamp:
                            needUpdate = True
                        index += 1
            except Exception as e:
                needUpdate = True
            if needUpdate:
                if os.path.exists(".data/storage/updater/{}/{}".format(args["stream"], "updating")):
                    log("Still updating, sending cache")
                    return Response(json.dumps(data))
                f = open(".data/storage/updater/{}/{}".format(args["stream"], "updating"), 'w')
                try:
                    log("[Aeris updater] New files detected, updating Downloadable files")
                    log("[AU] Clearing zip cache")
                except:
                    pass
                path = ".data/storage/updater/{}/zip".format(args["stream"])
                shutil.rmtree(path)
                os.mkdir(path)
                for x in neededFiles:
                    index = len(result)
                    result.append({})
                    file = ".data/storage/updater/{}/{}".format(args["stream"], x)

                    result[index]["filesize"] = os.stat(file).st_size
                    result[index]["file_version"] = str(index + 1)
                    result[index]["file_hash"] = fileMd5(file)
                    result[index]["url_full"] = "https://storage.kawata.pw/get/updater/{}/zip/{}".format(args["stream"], result[index]["file_hash"])
                    result[index]["patch_id"] = None
                    timestamp = os.path.getmtime(".data/storage/updater/{}/{}".format(args["stream"], x))
                    result[index]["timestamp"] = time.strftime('%m-%d-%Y %H:%M:%S', time.gmtime(timestamp))
                    result[index]["filename"] = x
                    zf = zipfile.ZipFile(".data/storage/updater/{}/zip/{}.zip".format(args["stream"], result[index]["file_hash"]), mode='w')
                    zf.write(file, arcname=x)
                    f = open(updaterCache, "w")
                    f.write(json.dumps(result))

                os.remove(".data/storage/updater/{}/{}".format(args["stream"], "updating"))
                log("[Aeris updater] Downloadable files updated")

            else:
                result = data

            return Response(json.dumps(result))
        except Exception as e:
            log(f"Error: {e}", Ansi.LRED, file="./.data/logs/updater.log")
            return Response("")
    else:
        log("[Aeris updater] unknown action type : {}".format(args["action"]), Ansi.YELLOW)
    return Response(b"")

""" Misc handlers """
def fileMd5(file_path: str) -> str:
    with open(file_path, "rb") as file:
        md5_hash = hashlib.md5()
        for chunk in iter(lambda: file.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


if app.settings.REDIRECT_OSU_URLS:
    
    async def osu_redirect(request: Request) -> Response:
        request_uri = request.url.path
        redirect_url = f"https://osu.ppy.sh{request_uri}"
        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    for pattern in (
        "/beatmapsets/{file_path:path}",
        "/beatmaps/{file_path:path}",
        "/community/forums/topics/{file_path:path}",
    ):
        router.get(pattern)(osu_redirect)



@router.get("/ss/{screenshot_id}.{extension}")
async def get_screenshot(
    screenshot_id: str = Path(..., pattern=r"[a-zA-Z0-9-_]{8}"),
    extension: Literal["jpg", "jpeg", "png"] = Path(...),
) -> Response:
    """Serve a screenshot from the server, by filename."""
    screenshot_path = SCREENSHOTS_PATH / f"{screenshot_id}.{extension}"

    if not screenshot_path.exists():
        return ORJSONResponse(
            content={"status": "Screenshot not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        path=screenshot_path,
        media_type=app.utils.get_media_type(extension),
    )


@router.get("/d/{map_set_id}")
async def get_osz(
    map_set_id: str = Path(...),
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
async def get_updated_beatmap(
    request: Request,
    map_filename: str,
    host: str = Header(...),
) -> Response:
    """Send the latest .osu file the server has for a given map."""
    if host == "osu.ppy.sh":
        return Response("bancho.py only supports the -devserver connection method")

    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['raw_path'].decode()}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )


@router.get("/p/doyoureallywanttoaskpeppy")
async def peppyDMHandler() -> Response:
    return Response(
        content=(
            b"This user's ID is usually peppy's (when on bancho), "
            b"and is blocked from being messaged by the osu! client."
        ),
    )


""" ingame registration """


@router.post("/users")
async def register_account(
    request: Request,
    username: str = Form(..., alias="user[username]"),
    email: str = Form(..., alias="user[user_email]"),
    pw_plaintext: str = Form(..., alias="user[password]"),
    check: int = Form(...),
    #
    # TODO: allow nginx to be optional
    forwarded_ip: str = Header(..., alias="X-Forwarded-For"),
    real_ip: str = Header(..., alias="X-Real-IP"),
) -> Response:
    if not all((username, email, pw_plaintext)):
        return Response(
            content=b"Missing required params",
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
        if await players_repo.fetch_one(name=username):
            errors["username"].append("Username already taken by another player.")

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.EMAIL.match(email):
        errors["user_email"].append("Invalid email syntax.")
    else:
        if await players_repo.fetch_one(email=email):
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
        pw_md5 = hashlib.md5(pw_plaintext.encode()).hexdigest().encode()
        pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
        app.state.cache.bcrypt[pw_bcrypt] = pw_md5  # cache result for login

        ip = app.state.services.ip_resolver.get_ip(request.headers)

        geoloc = await app.state.services.fetch_geoloc(ip, request.headers)
        country = geoloc["country"]["acronym"] if geoloc is not None else "XX"

        async with app.state.services.database.transaction():
            # add to `users` table.
            player = await players_repo.create(
                name=username,
                email=email,
                pw_bcrypt=pw_bcrypt,
                country=country,
            )

            # add to `stats` table.
            await stats_repo.create_all_modes(player_id=player["id"])

        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.registrations")

        log(f"<{username} ({player['id']})> has registered!", Ansi.LGREEN)

    return Response(content=b"ok")  # success


@router.post("/difficulty-rating")
async def difficultyRatingHandler(request: Request) -> Response:
    if app.settings.DEBUG and app.settings.DEBUG_LEADERBOARDS:
        # Print the request body
        body = await request.body()
        log(f"Request URL: {request.url}\nRequest Body: {body.decode()}", Ansi.LMAGENTA)

        # Print the request path
        print(f"Request Path: {request.url.path}")

    # Redirect the request
    return RedirectResponse(
        url=f"https://osu.ppy.sh{request.url.path}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
