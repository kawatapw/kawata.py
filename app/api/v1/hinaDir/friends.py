"""hinaDir: Friends & relationship API endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query
from fastapi.responses import ORJSONResponse
from fastapi.security import HTTPAuthorizationCredentials as HTTPCredentials
from fastapi.security import HTTPBearer

from app.logging import error_catcher
import app.state

router = APIRouter()
oauth2_scheme = HTTPBearer(auto_error=False)


@router.get("/get_friends_detailed")
@error_catcher
async def api_get_friends_detailed(
    scope: Literal["mutuals", "followers", "blocked", "all"],
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
):
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

    result = {}

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
        result["mutuals"] = [dict(row) for row in rows]

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
        result["followers"] = [dict(row) for row in rows]

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
        result["blocked"] = [dict(row) for row in rows]

    result["status"] = "success"
    return ORJSONResponse(result)


@router.post("/set_relationship")
@error_catcher
async def api_set_relationship(
    token: HTTPCredentials = Depends(oauth2_scheme),
    user_id: int = Query(..., alias="id", ge=2, le=2_147_483_647),
    target_id: int = Query(..., alias="target", ge=2, le=2_147_483_647),
    action: Literal["add_friend", "remove_friend", "block", "unblock"] = Query(...),
):
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
