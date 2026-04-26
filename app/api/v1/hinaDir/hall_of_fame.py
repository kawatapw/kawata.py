from __future__ import annotations

from typing import Any, Literal

import orjson
from fastapi import APIRouter
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse

import app.settings
import app.state
from app.constants.gamemodes import GameMode

router = APIRouter()

CACHE_KEY_PREFIX = "kawata:hall_of_fame:podium:v1"
CACHE_TTL_SECONDS = 900

_INVALID_MODES = {
    int(GameMode.RELAX_MANIA),
    int(GameMode.AUTOPILOT_TAIKO),
    int(GameMode.AUTOPILOT_CATCH),
    int(GameMode.AUTOPILOT_MANIA),
}


@router.get("/get_hall_of_fame_podium")
async def get_hall_of_fame_podium(
    mode: int = Query(0, ge=0, le=11),
    sort: Literal["pp", "rscore", "tscore", "acc", "plays", "playtime"] = "pp",
    country: str | None = Query(None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
) -> ORJSONResponse:
    if mode in _INVALID_MODES:
        return ORJSONResponse(
            {"status": "Invalid gamemode."},
            status_code=400,
        )

    country_norm = country.lower() if country else None
    country_key = country_norm if country_norm else "global"
    cache_key = f"{CACHE_KEY_PREFIX}:{mode}:{sort}:{country_key}"

    cached = await app.state.services.redis.get(cache_key)
    if cached is not None:
        return ORJSONResponse(orjson.loads(cached))

    where_conditions = [
        "s.mode = :mode",
        "s.season_id = 0",
        "u.priv & 1",
        "u.id != 1",
        f"s.{sort} > 0",
    ]
    where_params: dict[str, Any] = {"mode": int(mode)}

    if country_norm is not None:
        where_conditions.append("u.country = :country")
        where_params["country"] = country_norm

    where_clause = " AND ".join(where_conditions)

    # SQL safety (CodeRabbit: hall_of_fame.py raw SQL): `sort` is gated by
    # Pydantic Literal so only the 6 whitelisted column names ever reach
    # this f-string. `where_clause` only joins hardcoded condition snippets,
    # never user input. All user values flow via bound `:params`. No
    # injection surface — keeping raw SQL for parity with the rest of
    # `app/api/v1/` (Loki) and the rest of `hinaDir/`.
    rows = await app.state.services.database.fetch_all(
        "SELECT u.id AS player_id, u.name, u.country, "
        f"CONCAT('https://a.{app.settings.DOMAIN}/', u.id) AS avatar_url, "
        "s.tscore, s.rscore, s.pp, s.plays, s.playtime, s.acc, s.max_combo, "
        "s.xh_count, s.x_count, s.sh_count, s.s_count, s.a_count, "
        "c.id AS clan_id, c.name AS clan_name, c.tag AS clan_tag "
        "FROM stats s "
        "INNER JOIN users u ON u.id = s.id "
        "LEFT JOIN clans c ON u.clan_id = c.id "
        f"WHERE {where_clause} "  # noqa: E501  # nosec B608
        f"ORDER BY s.{sort} DESC LIMIT 3",  # noqa: E501  # nosec B608
        where_params,
    )
    rows = rows or []

    podium: list[dict[str, Any]] = [dict(row) for row in rows]

    if podium:
        ids = [int(p["player_id"]) for p in podium]
        placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))
        badge_params: dict[str, Any] = {f"id_{i}": pid for i, pid in enumerate(ids)}

        badge_rows = await app.state.services.database.fetch_all(
            "SELECT ub.userid, b.id AS badge_id, b.name, b.description, b.priority, "
            "bs.type AS style_type, bs.value AS style_value "
            "FROM user_badges ub "
            "INNER JOIN badges b ON b.id = ub.badge_id "
            "LEFT JOIN badge_styles bs ON bs.badge_id = ub.badge_id "
            f"WHERE ub.userid IN ({placeholders})",  # noqa: E501  # nosec B608
            badge_params,
        )
        badge_rows = badge_rows or []

        badges_by_user: dict[int, dict[int, dict[str, Any]]] = {}
        for row in badge_rows:
            user_id = int(row["userid"])
            badge_id = int(row["badge_id"])
            user_map = badges_by_user.setdefault(user_id, {})
            badge = user_map.setdefault(
                badge_id,
                {
                    "id": badge_id,
                    "name": row["name"],
                    "description": row["description"],
                    "priority": int(row["priority"]),
                    "styles": {},
                },
            )
            if row["style_type"] is not None:
                badge["styles"][row["style_type"]] = row["style_value"]

        for player in podium:
            user_id = int(player["player_id"])
            user_badges = list(badges_by_user.get(user_id, {}).values())
            user_badges.sort(key=lambda b: b["priority"], reverse=True)
            player["badges"] = user_badges

    payload = {
        "status": "success",
        "mode": int(mode),
        "sort": sort,
        "country": country_norm,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "podium": podium,
    }

    await app.state.services.redis.set(
        cache_key,
        orjson.dumps(payload),
        ex=CACHE_TTL_SECONDS,
    )

    return ORJSONResponse(payload)
