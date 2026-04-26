from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse

import app.constants.mods
import app.state
from app.constants.mods import Mods

router = APIRouter()


@router.get("/get_score_records")
async def get_score_records(
    mode: int = Query(0, ge=0, le=8),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    season_id: int | None = Query(None),
) -> ORJSONResponse:
    if season_id is not None and season_id < 0:
        return ORJSONResponse(
            {"status": "error", "message": "season_id must be a non-negative integer (0 = all-time)"},
            status_code=400,
        )

    where = "sc.mode = :mode AND sc.status = 2 AND u.priv & 1 AND sc.score > 0"
    where_params: dict[str, Any] = {"mode": mode}

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

    count_sql = (
        "SELECT COUNT(*) AS cnt "
        "FROM scores sc "
        "INNER JOIN users u ON u.id = sc.userid "
        "INNER JOIN maps m ON m.md5 = sc.map_md5 "
        f"WHERE {where}"
    )
    count_row = await app.state.services.database.fetch_one(count_sql, where_params)
    total = count_row["cnt"] if count_row else 0

    data_params = {**where_params, "limit": limit, "offset": offset}
    data_sql = (
        "SELECT sc.id, sc.score, sc.pp, sc.acc, sc.max_combo, sc.mods, sc.grade, "
        "sc.n300, sc.n100, sc.n50, sc.nmiss, sc.play_time, sc.perfect, "
        "sc.userid AS player_id, "
        "u.name AS player_name, u.country AS player_country, "
        "m.id AS map_id, m.set_id, m.artist, m.title, m.version, m.diff, m.max_combo AS map_max_combo "
        "FROM scores sc "
        "INNER JOIN users u ON u.id = sc.userid "
        "INNER JOIN maps m ON m.md5 = sc.map_md5 "
        f"WHERE {where} "
        "ORDER BY sc.score DESC "
        "LIMIT :offset, :limit"
    )
    rows = [dict(r) for r in (await app.state.services.database.fetch_all(data_sql, data_params) or [])]

    for row in rows:
        mods = Mods(row["mods"])
        mods_str = app.constants.mods.get_mods_string(mods)
        if "NC" in mods_str:
            mods_str = mods_str.replace("DT", "")
        if "PF" in mods_str:
            mods_str = mods_str.replace("SD", "")
        row["mods_readable"] = mods_str

    return ORJSONResponse(
        {"status": "success", "records": rows, "total": total},
    )
