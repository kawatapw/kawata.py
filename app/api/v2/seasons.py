"""
Seasons API v2 - Season Management and Statistics Endpoints

This module provides v2 API endpoints for managing and retrieving season
information, statistics, and schedules in the osu! server application. It
implements RESTful endpoints for season listing, individual season retrieval,
season statistics access, and season preference management.

The module uses the v2 API response format with standardized success and
failure responses, providing consistent error handling and metadata
for paginated results. It supports filtering by various season attributes
including schedule type, active status, and date ranges.

Key Features:
    - Paginated season listing with configurable page sizes
    - Individual season retrieval by ID
    - Season statistics with filtering by mode
    - Season preference management for players
    - Standardized v2 API response format
    - Type-safe response models using Pydantic
    - Integration with seasons repository

Integration Points:
    - Seasons data access in app/repositories/seasons.py
    - Statistics data access in app/repositories/stats.py
    - Response formatting in app/api/v2/common/responses.py
    - Data models in app/api/v2/models/seasons.py
    - FastAPI router for endpoint registration

Endpoints:
    - GET /seasons: List seasons with filtering and pagination
    - GET /seasons/{season_id}: Get specific season by ID
    - GET /seasons/{season_id}/stats: Get season statistics
    - GET /players/{player_id}/season-preference: Get player's season preference
    - POST /players/{player_id}/season-preference: Update player's season preference

Usage Pattern:
    # List seasons with pagination
    GET /api/v2/seasons?page=1&page_size=50

    # Get specific season
    GET /api/v2/seasons/1

    # Get season statistics
    GET /api/v2/seasons/1/stats?mode=0

    # Get player season preference
    GET /api/v2/players/12345/season-preference

    # Update player season preference
    POST /api/v2/players/12345/season-preference

Related Files:
    - app/repositories/seasons.py: Seasons data access layer
    - app/repositories/stats.py: Statistics data access layer
    - app/api/v2/models/seasons.py: Season data models
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.param_functions import Query
from fastapi.security import HTTPAuthorizationCredentials as HTTPCredentials
from fastapi.security import HTTPBearer

import app.state
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.seasons import Season
from app.api.v2.models.seasons import SeasonStats
from app.repositories import seasons as seasons_repo
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo

router = APIRouter()
http_bearer_scheme = HTTPBearer(auto_error=False)


@router.get("/seasons")
async def get_seasons(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Season]] | Failure:
    """List all seasons with pagination."""
    seasons = await seasons_repo.fetch_many(
        page=page,
        page_size=page_size,
    )
    total_seasons = await seasons_repo.fetch_count()

    response = [Season.from_mapping(rec) for rec in seasons]

    return responses.success(
        content=response,
        meta={
            "total": total_seasons,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/seasons/{season_id}")
async def get_season(season_id: int) -> Success[Season] | Failure:
    """Get a specific season by ID."""
    data = await seasons_repo.fetch_one(id=season_id)
    if data is None:
        return responses.failure(
            message="Season not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Season.from_mapping(data)
    return responses.success(response)


@router.get("/seasons/{season_id}/stats")
async def get_season_stats(
    season_id: int,
    mode: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[SeasonStats]] | Failure:
    """Get statistics for a specific season."""
    # Verify season exists
    season = await seasons_repo.fetch_one(id=season_id)
    if season is None:
        return responses.failure(
            message="Season not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    data = await stats_repo.fetch_many(
        season_id=season_id,
        mode=mode,
        page=page,
        page_size=page_size,
    )
    total_stats = await stats_repo.fetch_count(
        season_id=season_id,
        mode=mode,
    )

    response = [SeasonStats.from_mapping(rec) for rec in data]
    return responses.success(
        response,
        meta={
            "total": total_stats,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/players/{player_id}/season-preference")
async def get_season_preference(
    player_id: int,
) -> Success[dict[str, Any]] | Failure:
    """Get a player's season view preference."""
    data = await users_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return responses.success(
        {
            "player_id": player_id,
            "preferred_lb_view": data.get("preferred_lb_view", "all_time"),
        },
    )


@router.post("/players/{player_id}/season-preference")
async def update_season_preference(
    player_id: int,
    preferred_lb_view: str,
    token: HTTPCredentials | None = Depends(http_bearer_scheme),
) -> Success[dict[str, Any]] | Failure:
    """Update a player's season view preference."""
    if token is None or app.state.sessions.api_keys.get(token.credentials) is None:
        return responses.failure(
            message="Invalid API key.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if preferred_lb_view not in ("all_time", "seasonal"):
        return responses.failure(
            message="Invalid preference. Must be 'all_time' or 'seasonal'.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    data = await users_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    await users_repo.partial_update(
        id=player_id,
        preferred_lb_view=preferred_lb_view,
    )

    # Also update the live session if the player is online
    online_player = app.state.sessions.players.get(id=player_id)
    if online_player is not None:
        online_player.preferred_lb_view = preferred_lb_view

    return responses.success(
        {
            "player_id": player_id,
            "preferred_lb_view": preferred_lb_view,
        },
    )


@router.get("/schedules")
async def get_schedules() -> Success[list[dict[str, Any]]] | Failure:
    """List all season schedules."""
    schedules = await seasons_repo.fetch_many_schedules()

    response: list[dict[str, Any]] = []
    for schedule in schedules:
        response.append(
            {
                "id": schedule["id"],
                "name": schedule["name"],
                "description": schedule["description"],
                "schedule_type": schedule["schedule_type"],
                "is_default": schedule["is_default"],
                "created_at": (
                    schedule["created_at"].isoformat()
                    if schedule["created_at"] is not None
                    else None
                ),
            },
        )

    return responses.success(response)


@router.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: int) -> Success[dict[str, Any]] | Failure:
    """Get a specific schedule by ID."""
    schedule = await seasons_repo.fetch_schedule_by_id(schedule_id)
    if schedule is None:
        return responses.failure(
            message="Schedule not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return responses.success(
        {
            "id": schedule["id"],
            "name": schedule["name"],
            "description": schedule["description"],
            "schedule_type": schedule["schedule_type"],
            "config": schedule["config"],
            "is_default": schedule["is_default"],
            "created_at": (
                schedule["created_at"].isoformat()
                if schedule["created_at"] is not None
                else None
            ),
        },
    )


@router.get("/schedules/{schedule_id}/active-season")
async def get_active_season_for_schedule(
    schedule_id: int,
) -> Success[dict[str, Any]] | Failure:
    """Get the active season for a specific schedule."""
    schedule = await seasons_repo.fetch_schedule_by_id(schedule_id)
    if schedule is None:
        return responses.failure(
            message="Schedule not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    active_season = await seasons_repo.fetch_active_season_by_schedule(schedule_id)
    if active_season is None:
        return responses.failure(
            message="No active season found for this schedule.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return responses.success(
        {
            "id": active_season["id"],
            "name": active_season["name"],
            "schedule_id": active_season["schedule_id"],
            "start_date": active_season["start_date"].isoformat(),
            "end_date": active_season["end_date"].isoformat(),
            "is_active": active_season["is_active"],
        },
    )


@router.put("/players/{player_id}/preferred-schedule")
async def set_preferred_schedule(
    player_id: int,
    schedule_id: int,
    token: HTTPCredentials | None = Depends(http_bearer_scheme),
) -> Success[dict[str, Any]] | Failure:
    """Set a player's preferred schedule type.

    Args:
        player_id: The player's ID
        schedule_id: The schedule ID to set as preferred, or None to clear preference
    """
    if token is None or app.state.sessions.api_keys.get(token.credentials) is None:
        return responses.failure(
            message="Invalid API key.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    data = await users_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Validate schedule exists if provided
    # Note: schedule_id is a path parameter, so it's always provided
    schedule = await seasons_repo.fetch_schedule_by_id(schedule_id)
    if schedule is None:
        return responses.failure(
            message="Schedule not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    await users_repo.partial_update(
        id=player_id,
        preferred_schedule_id=schedule_id,
    )

    # Also update the live session if the player is online
    online_player = app.state.sessions.players.get(id=player_id)
    if online_player is not None:
        online_player.preferred_schedule_id = schedule_id

    return responses.success(
        {
            "player_id": player_id,
            "preferred_schedule_id": schedule_id,
        },
    )


@router.get("/players/{player_id}/preferred-schedule")
async def get_preferred_schedule(
    player_id: int,
) -> Success[dict[str, Any]] | Failure:
    """Get a player's preferred schedule type."""
    data = await users_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    preferred_schedule_id: int | None = data.get("preferred_schedule_id")
    schedule_info = None

    if preferred_schedule_id is not None:
        schedule = await seasons_repo.fetch_schedule_by_id(preferred_schedule_id)
        if schedule:
            schedule_info = {
                "id": schedule["id"],
                "name": schedule["name"],
                "schedule_type": schedule["schedule_type"],
            }

    return responses.success(
        {
            "player_id": player_id,
            "preferred_schedule_id": preferred_schedule_id,
            "schedule": schedule_info,
        },
    )
