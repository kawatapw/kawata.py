from __future__ import annotations

from typing import Any

import orjson
from fastapi import APIRouter
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse

import app.state
from app.api.v1.hinaDir._cover_urls import cover_urls

router = APIRouter()

CACHE_KEY_PREFIX = "kawata:hero_banners:v2"
CACHE_TTL_SECONDS = 3600
PLAYS_NOISE_FLOOR = 5

HERO_SQL = """
SELECT
    m.set_id AS set_id,
    MAX(m.artist) AS artist,
    MAX(m.title) AS title,
    MAX(m.creator) AS creator,
    MAX(m.mode) AS mode,
    MAX(m.status) AS max_status,
    SUM(m.plays) AS total_plays,
    SUM(m.passes) AS total_passes,
    COUNT(m.id) AS diff_count,
    COALESCE(MAX(f.fav_count), 0) AS fav_count,
    SUM(m.plays) + COALESCE(MAX(f.fav_count), 0) * 500 AS hero_score
FROM maps m
LEFT JOIN (
    SELECT setid, COUNT(*) AS fav_count
    FROM favourites
    GROUP BY setid
) f ON f.setid = m.set_id
WHERE m.plays > :noise_floor
GROUP BY m.set_id
HAVING SUM(m.plays) > :noise_floor
ORDER BY hero_score DESC
LIMIT :limit
"""


@router.get("/get_hero_banners")
async def get_hero_banners(
    limit: int = Query(50, ge=1, le=100),
) -> ORJSONResponse:
    cache_key = f"{CACHE_KEY_PREFIX}:{limit}"

    cached = await app.state.services.redis.get(cache_key)
    if cached is not None:
        return ORJSONResponse(orjson.loads(cached))

    rows = await app.state.services.database.fetch_all(
        HERO_SQL,
        {"limit": limit, "noise_floor": PLAYS_NOISE_FLOOR},
    )

    banners: list[dict[str, Any]] = []
    for row in rows or []:
        set_id = int(row["set_id"])
        banners.append({
            "set_id": set_id,
            "artist": row["artist"],
            "title": row["title"],
            "creator": row["creator"],
            "mode": int(row["mode"]),
            "status": int(row["max_status"]),
            "total_plays": int(row["total_plays"]),
            "total_passes": int(row["total_passes"]),
            "diff_count": int(row["diff_count"]),
            "fav_count": int(row["fav_count"]),
            "hero_score": int(row["hero_score"]),
            **cover_urls(set_id),
        })

    payload = {
        "status": "success",
        "count": len(banners),
        "limit": limit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "banners": banners,
    }

    await app.state.services.redis.set(
        cache_key,
        orjson.dumps(payload),
        ex=CACHE_TTL_SECONDS,
    )

    return ORJSONResponse(payload)
