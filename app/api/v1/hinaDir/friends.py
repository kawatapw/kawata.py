"""hinaDir: Friends & relationship API endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse
from fastapi.security import HTTPAuthorizationCredentials as HTTPCredentials
from fastapi.security import HTTPBearer

from app.logging import error_catcher
import app.settings
import app.state

router = APIRouter()
oauth2_scheme = HTTPBearer(auto_error=False)


def _enrich_with_status(user_row: dict[str, Any]) -> dict[str, Any]:
    """Add is_online + player_status to a user dict by checking in-memory sessions."""
    player = app.state.sessions.players.get(id=user_row["id"])
    if player and player.is_online:
        user_row["is_online"] = True
        user_row["player_status"] = {
            "action": player.status.action.value,
            "action_name": player.status.action.name,
            "info_text": player.status.info_text,
            "mode": player.status.mode.value,
            "mods": int(player.status.mods),
            "map_id": player.status.map_id,
        }
    else:
        user_row["is_online"] = False
        user_row["player_status"] = None
    return user_row


@router.get("/get_friends_detailed")
@error_catcher
async def api_get_friends_detailed(
    scope: Literal["mutuals", "followers", "blocked", "all"],
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
) -> ORJSONResponse:
    """Returns detailed friend/follower/block info for a given user."""
    # Verify user exists
    user = await app.state.services.database.fetch_one(
        "SELECT id FROM users WHERE id = :id AND priv & 1",
        {"id": user_id},
    )
    if not user:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    result: dict[str, Any] = {}

    if scope in ("mutuals", "all"):
        rows = await app.state.services.database.fetch_all(
            "SELECT u.id, u.name, u.safe_name, u.country, u.priv, u.latest_activity, "
            "c.name AS clan_name, c.tag AS clan_tag "
            "FROM relationships r1 "
            "INNER JOIN relationships r2 ON r1.user2 = r2.user1 AND r1.user1 = r2.user2 "
            "INNER JOIN users u ON u.id = r1.user2 "
            "LEFT JOIN clans c ON u.clan_id = c.id "
            "WHERE r1.user1 = :user_id AND r1.type = 'friend' AND r2.type = 'friend' "
            "AND u.priv & 1 = 1",
            {"user_id": user_id},
        )
        result["mutuals"] = [_enrich_with_status(dict(row)) for row in rows] if rows else []

    if scope in ("followers", "all"):
        rows = await app.state.services.database.fetch_all(
            "SELECT u.id, u.name, u.safe_name, u.country, u.priv, u.latest_activity, "
            "c.name AS clan_name, c.tag AS clan_tag "
            "FROM relationships r1 "
            "INNER JOIN users u ON u.id = r1.user1 "
            "LEFT JOIN clans c ON u.clan_id = c.id "
            "WHERE r1.user2 = :user_id AND r1.type = 'friend' "
            "AND r1.user1 NOT IN ("
            "  SELECT user2 FROM relationships WHERE user1 = :user_id AND type = 'friend'"
            ") "
            "AND u.priv & 1 = 1",
            {"user_id": user_id},
        )
        result["followers"] = [_enrich_with_status(dict(row)) for row in rows] if rows else []

    if scope in ("blocked", "all"):
        rows = await app.state.services.database.fetch_all(
            "SELECT u.id, u.name, u.safe_name, u.country, u.priv, u.latest_activity, "
            "c.name AS clan_name, c.tag AS clan_tag "
            "FROM relationships r1 "
            "INNER JOIN users u ON u.id = r1.user2 "
            "LEFT JOIN clans c ON u.clan_id = c.id "
            "WHERE r1.user1 = :user_id AND r1.type = 'block' "
            "AND u.priv & 1 = 1",
            {"user_id": user_id},
        )
        result["blocked"] = [_enrich_with_status(dict(row)) for row in rows] if rows else []

    result["status"] = "success"
    return ORJSONResponse(result)


@router.get("/get_friends_status")
@error_catcher
async def api_get_friends_status(
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
) -> ORJSONResponse:
    """Lightweight polling endpoint: returns only online status for a user's friends."""
    friend_rows = await app.state.services.database.fetch_all(
        "SELECT user2 FROM relationships WHERE user1 = :uid AND type = 'friend'",
        {"uid": user_id},
    )

    online = {}
    if friend_rows:
        for row in friend_rows:
            fid = row["user2"]
            player = app.state.sessions.players.get(id=fid)
            if player and player.is_online:
                online[str(fid)] = {
                    "action": player.status.action.value,
                    "action_name": player.status.action.name,
                    "info_text": player.status.info_text,
                    "mode": player.status.mode.value,
                    "mods": int(player.status.mods),
                    "map_id": player.status.map_id,
                }

    return ORJSONResponse({"status": "success", "online": online})


@router.post("/set_relationship")
@error_catcher
async def api_set_relationship(
    token: HTTPCredentials | None = Depends(oauth2_scheme),
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
    target_id: int = Query(..., alias="target", ge=2, le=2_147_483_647),
    action: Literal["add_friend", "remove_friend", "block", "unblock"] = Query(...),
) -> ORJSONResponse:
    """Add/remove friends or block/unblock users. Requires BOT_API_KEY."""
    if token is None or token.credentials != app.settings.BOT_API_KEY:
        return ORJSONResponse(
            {"status": "Unauthorized."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if user_id == target_id:
        return ORJSONResponse(
            {"status": "Cannot target yourself."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Verify target user exists
    target = await app.state.services.database.fetch_one(
        "SELECT id FROM users WHERE id = :id AND priv & 1",
        {"id": target_id},
    )
    if not target:
        return ORJSONResponse(
            {"status": "Target user not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if action == "add_friend":
        await app.state.services.database.execute(
            "REPLACE INTO relationships (user1, user2, type) VALUES (:u1, :u2, 'friend')",
            {"u1": user_id, "u2": target_id},
        )
        # Update in-memory state if player is online
        if p := app.state.sessions.players.get(id=user_id):
            p.friends.add(target_id)
            p.blocks.discard(target_id)

    elif action == "remove_friend":
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :u1 AND user2 = :u2 AND type = 'friend'",
            {"u1": user_id, "u2": target_id},
        )
        if p := app.state.sessions.players.get(id=user_id):
            p.friends.discard(target_id)

    elif action == "block":
        await app.state.services.database.execute(
            "REPLACE INTO relationships (user1, user2, type) VALUES (:u1, :u2, 'block')",
            {"u1": user_id, "u2": target_id},
        )
        if p := app.state.sessions.players.get(id=user_id):
            p.blocks.add(target_id)
            p.friends.discard(target_id)

    elif action == "unblock":
        await app.state.services.database.execute(
            "DELETE FROM relationships WHERE user1 = :u1 AND user2 = :u2 AND type = 'block'",
            {"u1": user_id, "u2": target_id},
        )
        if p := app.state.sessions.players.get(id=user_id):
            p.blocks.discard(target_id)

    return ORJSONResponse({"status": "success"})


@router.get("/get_friends_leaderboard")
@error_catcher
async def api_get_friends_leaderboard(
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
    mode: int = Query(0, ge=0, le=3),
    season_id: int | None = Query(None, alias="season_id"),
) -> ORJSONResponse:
    """Returns mutual friends + self ranked by PP for a given game mode."""
    # Get mutual friend IDs (bidirectional)
    mutual_rows = await app.state.services.database.fetch_all(
        "SELECT r1.user2 AS id "
        "FROM relationships r1 "
        "INNER JOIN relationships r2 ON r1.user2 = r2.user1 AND r1.user1 = r2.user2 "
        "WHERE r1.user1 = :user_id AND r1.type = 'friend' AND r2.type = 'friend'",
        {"user_id": user_id},
    )

    # Build ID list: mutual friends + requesting user
    ids = [row["id"] for row in mutual_rows] if mutual_rows else []
    ids.append(user_id)
    ids = list(set(ids))

    if not ids:
        return ORJSONResponse({"status": "success", "leaderboard": []})

    # Build dynamic placeholders for IN clause
    placeholders = ",".join(f":id_{i}" for i in range(len(ids)))
    params = {f"id_{i}": uid for i, uid in enumerate(ids)}
    params["mode"] = mode

    params["season_id"] = season_id if season_id else 0
    rows = await app.state.services.database.fetch_all(
        "SELECT u.id, u.name, u.country, u.priv, "
        "c.tag AS clan_tag, "
        "COALESCE(s.pp, 0) AS pp, COALESCE(s.acc, 0) AS acc, COALESCE(s.plays, 0) AS plays "
        "FROM users u "
        "LEFT JOIN stats s ON s.id = u.id AND s.mode = :mode AND s.season_id = :season_id "
        "LEFT JOIN clans c ON u.clan_id = c.id "
        f"WHERE u.id IN ({placeholders}) "
        "AND u.priv & 1 "
        "ORDER BY pp DESC "
        "LIMIT 50",
        params,
    )

    leaderboard = []
    if rows:
        for i, row in enumerate(rows):
            entry = dict(row)
            entry["rank"] = i + 1

            # Get global rank from Redis (season-aware)
            sid = params["season_id"]
            lb_key = f"bancho:leaderboard:{mode}" if not sid else f"bancho:leaderboard:{mode}:season:{sid}"
            global_rank = await app.state.services.redis.zrevrank(
                lb_key,
                str(entry["id"]),
            )
            entry["global_rank"] = (global_rank + 1) if global_rank is not None else 0

            entry["is_online"] = False
            player = app.state.sessions.players.get(id=entry["id"])
            if player and player.is_online:
                entry["is_online"] = True

            # Cast Decimal→native Python types for JSON serialization
            entry["pp"] = float(entry["pp"])
            entry["acc"] = round(float(entry["acc"]), 2)
            entry["plays"] = int(entry["plays"])

            leaderboard.append(entry)

    # Add PP delta between consecutive ranks
    for i, entry in enumerate(leaderboard):
        if i == 0:
            if len(leaderboard) > 1:
                entry["pp_delta"] = {
                    "value": round(entry["pp"] - leaderboard[1]["pp"]),
                    "type": "lead",
                }
            else:
                entry["pp_delta"] = None
        else:
            delta = round(leaderboard[i - 1]["pp"] - entry["pp"])
            entry["pp_delta"] = {
                "value": delta,
                "type": "tie" if delta == 0 else "chase",
            }

    return ORJSONResponse({"status": "success", "leaderboard": leaderboard})


@router.get("/get_player_quick_stats")
@error_catcher
async def api_get_player_quick_stats(
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
    mode: int = Query(0, ge=0, le=3),
    season_id: int | None = Query(None, alias="season_id"),
) -> ORJSONResponse:
    """Lightweight endpoint returning extra stats + top play for one player."""
    # Fetch stats
    sid = season_id if season_id else 0
    stats_row = await app.state.services.database.fetch_one(
        "SELECT s.pp, s.acc, s.plays, s.playtime, s.max_combo, "
        "s.tscore, s.rscore, "
        "s.xh_count, s.x_count, s.sh_count, s.s_count, s.a_count "
        "FROM stats s "
        "INNER JOIN users u ON u.id = s.id "
        "WHERE s.id = :uid AND s.mode = :mode AND s.season_id = :season_id AND u.priv & 1",
        {"uid": user_id, "mode": mode, "season_id": sid},
    )

    if not stats_row:
        return ORJSONResponse(
            {"status": "Player not found."},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    stats = dict(stats_row)
    stats["pp"] = float(stats["pp"])
    stats["acc"] = round(float(stats["acc"]), 2)
    stats["tscore"] = int(stats["tscore"])
    stats["rscore"] = int(stats["rscore"])

    # Global rank from Redis (season-aware)
    lb_key = f"bancho:leaderboard:{mode}" if not sid else f"bancho:leaderboard:{mode}:season:{sid}"
    global_rank = await app.state.services.redis.zrevrank(
        lb_key,
        str(user_id),
    )
    stats["global_rank"] = (global_rank + 1) if global_rank is not None else 0

    # Top play (single best score with map title, season-scoped)
    top_query = (
        "SELECT t.pp, t.acc, t.grade, t.mods, "
        "CONCAT(b.artist, ' - ', b.title, ' [', b.version, ']') AS map_title "
        "FROM scores t "
        "INNER JOIN maps b ON t.map_md5 = b.md5 "
        "WHERE t.userid = :uid AND t.mode = :mode AND t.status = 2 "
        "AND b.status IN (2, 3) "
    )
    top_params: dict[str, object] = {"uid": user_id, "mode": mode}
    if sid:
        from app.repositories import seasons as seasons_repo

        season = await seasons_repo.fetch_one(id=sid)
        if season:
            top_query += "AND t.play_time >= :start_date AND t.play_time < :end_date "
            top_params["start_date"] = season["start_date"]
            top_params["end_date"] = season["end_date"]
    top_query += "ORDER BY t.pp DESC LIMIT 1"
    top_row = await app.state.services.database.fetch_one(top_query, top_params)

    top_play = None
    if top_row:
        top = dict(top_row)
        top["pp"] = float(top["pp"])
        top["acc"] = round(float(top["acc"]), 2)
        top_play = top

    return ORJSONResponse({
        "status": "success",
        "stats": stats,
        "top_play": top_play,
    })


async def _get_player_stats(uid: int, mode: int, season_id: int = 0) -> dict[str, Any] | None:
    """Fetch a single player's stats for a given mode and season."""
    row = await app.state.services.database.fetch_one(
        "SELECT s.id, u.name, u.country, "
        "c.tag AS clan_tag, "
        "s.pp, s.acc, s.plays, s.max_combo, "
        "s.xh_count, s.x_count, s.sh_count, s.s_count, s.a_count "
        "FROM stats s "
        "INNER JOIN users u ON u.id = s.id "
        "LEFT JOIN clans c ON u.clan_id = c.id "
        "WHERE s.id = :uid AND s.mode = :mode AND s.season_id = :season_id AND u.priv & 1",
        {"uid": uid, "mode": mode, "season_id": season_id},
    )

    if row:
        entry = dict(row)
        entry["pp"] = float(entry["pp"])
        entry["acc"] = float(entry["acc"])
        entry["has_stats"] = entry["pp"] > 0
    else:
        # User exists but no stats for this mode — return zeroes
        user_row = await app.state.services.database.fetch_one(
            "SELECT id, name, country FROM users WHERE id = :uid AND priv & 1",
            {"uid": uid},
        )
        if not user_row:
            return None
        entry = {
            "id": user_row["id"],
            "name": user_row["name"],
            "country": user_row["country"],
            "clan_tag": None,
            "pp": 0,
            "acc": 0.0,
            "plays": 0,
            "max_combo": 0,
            "xh_count": 0,
            "x_count": 0,
            "sh_count": 0,
            "s_count": 0,
            "a_count": 0,
            "has_stats": False,
        }

    # Global rank from Redis (season-aware)
    lb_key = f"bancho:leaderboard:{mode}" if not season_id else f"bancho:leaderboard:{mode}:season:{season_id}"
    global_rank = await app.state.services.redis.zrevrank(
        lb_key,
        str(entry["id"]),
    )
    entry["rank"] = (global_rank + 1) if global_rank is not None else 0
    entry["acc"] = round(float(entry.get("acc", 0)), 2)

    return entry


@router.get("/compare_stats")
@error_catcher
async def api_compare_stats(
    users: str = Query(...),
    mode: int = Query(0, ge=0, le=3),
    season_id: int | None = Query(None, alias="season_id"),
) -> ORJSONResponse:
    """Returns stats comparison for 2-4 players."""
    try:
        user_ids = [int(x.strip()) for x in users.split(",")]
    except ValueError:
        return ORJSONResponse(
            {"status": "Invalid user IDs."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if len(user_ids) < 2 or len(user_ids) > 4:
        return ORJSONResponse(
            {"status": "Provide 2-4 user IDs."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Deduplicate while preserving order
    seen: set[int] = set()
    unique_ids: list[int] = []
    for uid in user_ids:
        if uid not in seen:
            seen.add(uid)
            unique_ids.append(uid)

    if len(unique_ids) < 2:
        return ORJSONResponse(
            {"status": "Provide 2-4 distinct user IDs."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    players = []
    for uid in unique_ids:
        p = await _get_player_stats(uid, mode, season_id if season_id else 0)
        if p is None:
            return ORJSONResponse(
                {"status": "Player not found."},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        players.append(p)

    return ORJSONResponse({"status": "success", "players": players})
