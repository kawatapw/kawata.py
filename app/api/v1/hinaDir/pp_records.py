"""hinaDir: PP Records API endpoint."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse

from app.constants.mods import Mods
import app.constants.mods
import app.state

router = APIRouter()

VALID_CHEAT_TYPES = frozenset({
    "Timewarp", "TimewarpType", "TimewarpRate", "TimewarpMultiplier",
    "AimType", "AimCorrectionValue", "TapOnCorrect", "TimesCorrected",
    "RelaxHack", "RelaxHackType",
    "HiddenRemover",
    "ARChanger", "ARChangerAR",
    "CSChanger", "CSChangerType",
})


@router.get("/get_pp_records")
async def get_pp_records(
    mode: int = Query(0, ge=0, le=8),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    cheat_type: str | None = Query(None),
    cheat_min: float | None = Query(None),
    cheat_max: float | None = Query(None),
    season_id: int | None = Query(None),
) -> ORJSONResponse:
    # Validate cheat_type against whitelist (prevent JSON path injection)
    if cheat_type is not None and cheat_type not in VALID_CHEAT_TYPES:
        return ORJSONResponse(
            {"status": "error", "message": "Invalid cheat_type"},
            status_code=400,
        )

    # Build WHERE clause
    where = "sc.mode = :mode AND sc.status = 2 AND u.priv & 1 AND sc.pp > 0"
    where_params: dict[str, Any] = {"mode": mode}

    # Season filter — scores table has no season_id, so filter by date range
    if season_id is not None and season_id > 0:
        season_row = await app.state.services.database.fetch_one(
            "SELECT start_date, end_date FROM seasons WHERE id = :sid",
            {"sid": season_id},
        )
        if season_row is None:
            return ORJSONResponse(
                {"status": "error", "message": "Season not found"},
                status_code=404,
            )
        where += " AND sc.play_time >= :season_start AND sc.play_time < :season_end"
        where_params["season_start"] = season_row["start_date"]
        where_params["season_end"] = season_row["end_date"]

    if cheat_type is not None:
        where += (
            " AND si.cheat_values IS NOT NULL"
            " AND JSON_EXTRACT(JSON_UNQUOTE(si.cheat_values), CONCAT('$.', :cheat_type)) IS NOT NULL"
        )
        where_params["cheat_type"] = cheat_type

        if cheat_min is not None:
            where += (
                " AND CAST(JSON_EXTRACT(JSON_UNQUOTE(si.cheat_values),"
                " CONCAT('$.', :cheat_type_min)) AS DECIMAL(10,2)) >= :cheat_min"
            )
            where_params["cheat_type_min"] = cheat_type
            where_params["cheat_min"] = cheat_min

        if cheat_max is not None:
            where += (
                " AND CAST(JSON_EXTRACT(JSON_UNQUOTE(si.cheat_values),"
                " CONCAT('$.', :cheat_type_max)) AS DECIMAL(10,2)) <= :cheat_max"
            )
            where_params["cheat_type_max"] = cheat_type
            where_params["cheat_max"] = cheat_max

    # Count query
    count_sql = (
        "SELECT COUNT(*) AS cnt "
        "FROM scores sc "
        "INNER JOIN users u ON u.id = sc.userid "
        "INNER JOIN maps m ON m.md5 = sc.map_md5 "
        "LEFT JOIN scoreinfo si ON si.scoreid = sc.id "
        f"WHERE {where}"
    )
    count_row = await app.state.services.database.fetch_one(count_sql, where_params)
    total = count_row["cnt"] if count_row else 0

    # Data query
    data_params = {**where_params, "limit": limit, "offset": offset}
    data_sql = (
        "SELECT sc.id, sc.pp, sc.acc, sc.max_combo, sc.mods, sc.grade, "
        "sc.n300, sc.n100, sc.n50, sc.nmiss, sc.play_time, "
        "sc.userid AS player_id, "
        "u.name AS player_name, u.country AS player_country, "
        "m.id AS map_id, m.set_id, m.artist, m.title, m.version, m.diff, "
        "si.cheat_values "
        "FROM scores sc "
        "INNER JOIN users u ON u.id = sc.userid "
        "INNER JOIN maps m ON m.md5 = sc.map_md5 "
        "LEFT JOIN scoreinfo si ON si.scoreid = sc.id "
        f"WHERE {where} "
        "ORDER BY sc.pp DESC "
        "LIMIT :offset, :limit"
    )
    rows = [dict(r) for r in (await app.state.services.database.fetch_all(data_sql, data_params) or [])]

    # Post-process rows
    for row in rows:
        # mods_readable (NC implies DT, PF implies SD — hide the redundant one)
        mods = Mods(row["mods"])
        mods_str = app.constants.mods.get_mods_string(mods)
        if "NC" in mods_str:
            mods_str = mods_str.replace("DT", "")
        if "PF" in mods_str:
            mods_str = mods_str.replace("SD", "")
        row["mods_readable"] = mods_str

        # Double-decode cheat_values
        if row["cheat_values"]:
            try:
                row["cheat_values"] = json.loads(json.loads(row["cheat_values"]))
            except (TypeError, json.JSONDecodeError):
                row["cheat_values"] = {}
        else:
            row["cheat_values"] = {}

    return ORJSONResponse(
        {"status": "success", "records": rows, "total": total},
    )
