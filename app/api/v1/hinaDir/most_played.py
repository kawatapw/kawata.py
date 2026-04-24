from __future__ import annotations

from typing import Any

import orjson
from fastapi import APIRouter
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse

import app.state

router = APIRouter()

CACHE_KEY_PREFIX = "kawata:most_played:v1"
CACHE_TTL_SECONDS = 600
PLAYS_NOISE_FLOOR = 0

MOST_PLAYED_SQL = """
SELECT
    m.id AS map_id,
    m.set_id AS set_id,
    m.md5 AS md5,
    m.artist AS artist,
    m.title AS title,
    m.version AS version,
    m.creator AS creator,
    m.plays AS plays,
    m.passes AS passes,
    m.mode AS mode,
    m.status AS status,
    m.diff AS diff,
    m.bpm AS bpm,
    m.cs AS cs,
    m.ar AS ar,
    m.od AS od,
    m.hp AS hp,
    m.max_combo AS max_combo,
    m.total_length AS total_length
FROM maps m
WHERE m.mode = :mode
  AND m.plays > :noise_floor
ORDER BY m.plays DESC
LIMIT :limit
"""


def _cover_urls(set_id: int) -> dict[str, str]:
    base = f"https://assets.ppy.sh/beatmaps/{set_id}/covers"
    return {
        "cover_url": f"{base}/cover@2x.jpg",
        "thumbnail_url": f"{base}/card@2x.jpg",
        "list_url": f"{base}/list@2x.jpg",
    }


@router.get("/get_most_played")
async def get_most_played(
    mode: int = Query(0, ge=0, le=8),
    limit: int = Query(100, ge=1, le=200),
) -> ORJSONResponse:
    cache_key = f"{CACHE_KEY_PREFIX}:{mode}:{limit}"

    cached = await app.state.services.redis.get(cache_key)
    if cached is not None:
        return ORJSONResponse(orjson.loads(cached))

    rows = await app.state.services.database.fetch_all(
        MOST_PLAYED_SQL,
        {"mode": mode, "limit": limit, "noise_floor": PLAYS_NOISE_FLOOR},
    )

    maps_list: list[dict[str, Any]] = []
    for row in rows or []:
        set_id = int(row["set_id"])
        maps_list.append({
            "map_id": int(row["map_id"]),
            "set_id": set_id,
            "md5": row["md5"],
            "artist": row["artist"],
            "title": row["title"],
            "version": row["version"],
            "creator": row["creator"],
            "plays": int(row["plays"]),
            "passes": int(row["passes"]),
            "mode": int(row["mode"]),
            "status": int(row["status"]),
            "diff": float(row["diff"]),
            "bpm": float(row["bpm"]),
            "cs": float(row["cs"]),
            "ar": float(row["ar"]),
            "od": float(row["od"]),
            "hp": float(row["hp"]),
            "max_combo": int(row["max_combo"]),
            "total_length": int(row["total_length"]),
            **_cover_urls(set_id),
        })

    payload = {
        "status": "success",
        "mode": mode,
        "count": len(maps_list),
        "limit": limit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "maps": maps_list,
    }

    await app.state.services.redis.set(
        cache_key,
        orjson.dumps(payload),
        ex=CACHE_TTL_SECONDS,
    )

    return ORJSONResponse(payload)
