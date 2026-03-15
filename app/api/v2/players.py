"""
Players API v2 - Player Management and Statistics Endpoints

This module provides v2 API endpoints for managing and retrieving player
information, statistics, and status in the osu! server application. It
implements RESTful endpoints for player listing, individual player retrieval,
status checking, and statistics access with comprehensive filtering and
pagination support.

The module uses the v2 API response format with standardized success and
failure responses, providing consistent error handling and metadata
for paginated results. It supports filtering by various player attributes
including privileges, country, clan membership, and game preferences.

Key Features:
    - Paginated player listing with configurable page sizes
    - Comprehensive filtering by multiple player attributes
    - Individual player retrieval by ID
    - Real-time player status checking
    - Game mode-specific statistics retrieval
    - All-mode statistics with pagination
    - Standardized v2 API response format
    - Type-safe response models using Pydantic
    - Integration with user and statistics repositories

Integration Points:
    - Player session management in app/state/sessions.py
    - User data access in app/repositories/users.py
    - Statistics data access in app/repositories/stats.py
    - Response formatting in app/api/v2/common/responses.py
    - Data models in app/api/v2/models/players.py
    - FastAPI router for endpoint registration

Endpoints:
    - GET /players: List players with filtering and pagination
    - GET /players/{player_id}: Get specific player by ID
    - GET /players/{player_id}/status: Get player's current status
    - GET /players/{player_id}/stats/{mode}: Get player stats for specific mode
    - GET /players/{player_id}/stats: Get all player stats with pagination

Filtering Options:
    - priv: Filter by privilege level
    - country: Filter by country code
    - clan_id: Filter by clan membership
    - clan_priv: Filter by clan privilege level
    - preferred_mode: Filter by preferred game mode
    - play_style: Filter by play style

Usage Pattern:
    # List players with pagination
    GET /api/v2/players?page=1&page_size=50
    
    # Filter by country and privileges
    GET /api/v2/players?country=US&priv=3
    
    # Get specific player
    GET /api/v2/players/12345
    
    # Get player status
    GET /api/v2/players/12345/status
    
    # Get player stats for specific mode
    GET /api/v2/players/12345/stats/0
    
    # Get all player stats
    GET /api/v2/players/12345/stats?page=1&page_size=10

Related Files:
    - app/repositories/users.py: User data access layer
    - app/repositories/stats.py: Statistics data access layer
    - app/api/v2/models/players.py: Player data models
    - app/api/v2/common/responses.py: Response formatting utilities
    - app/state/sessions.py: Player session management
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

import app.state.sessions
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.players import Player
from app.api.v2.models.players import PlayerStats
from app.api.v2.models.players import PlayerStatus
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo

router = APIRouter()


@router.get("/players")
async def get_players(
    priv: int | None = None,
    country: str | None = None,
    clan_id: int | None = None,
    clan_priv: int | None = None,
    preferred_mode: int | None = None,
    play_style: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Player]] | Failure:
    players = await users_repo.fetch_many(
        priv=priv,
        country=country,
        clan_id=clan_id,
        clan_priv=clan_priv,
        preferred_mode=preferred_mode,
        play_style=play_style,
        page=page,
        page_size=page_size,
    )
    total_players = await users_repo.fetch_count(
        priv=priv,
        country=country,
        clan_id=clan_id,
        clan_priv=clan_priv,
        preferred_mode=preferred_mode,
        play_style=play_style,
    )

    response = [Player.from_mapping(rec) for rec in players]

    return responses.success(
        content=response,
        meta={
            "total": total_players,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/players/{player_id}")
async def get_player(player_id: int) -> Success[Player] | Failure:
    data = await users_repo.fetch_one(id=player_id)
    if data is None:
        return responses.failure(
            message="Player not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Player.from_mapping(data)
    return responses.success(response)


@router.get("/players/{player_id}/status")
async def get_player_status(player_id: int) -> Success[PlayerStatus] | Failure:
    player = app.state.sessions.players.get(id=player_id)

    if not player:
        return responses.failure(
            message="Player status not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStatus(
        login_time=int(player.login_time),
        action=int(player.status.action),
        info_text=player.status.info_text,
        mode=int(player.status.mode),
        mods=int(player.status.mods),
        beatmap_id=player.status.map_id,
    )
    return responses.success(response)


@router.get("/players/{player_id}/stats/{mode}")
async def get_player_mode_stats(
    player_id: int,
    mode: int,
) -> Success[PlayerStats] | Failure:
    data = await stats_repo.fetch_one(player_id, mode)
    if data is None:
        return responses.failure(
            message="Player stats not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = PlayerStats.from_mapping(data)
    return responses.success(response)


@router.get("/players/{player_id}/stats")
async def get_player_stats(
    player_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[PlayerStats]] | Failure:
    data = await stats_repo.fetch_many(
        player_id=player_id,
        page=page,
        page_size=page_size,
    )
    total_stats = await stats_repo.fetch_count(
        player_id=player_id,
    )

    response = [PlayerStats.from_mapping(rec) for rec in data]
    return responses.success(
        response,
        meta={
            "total": total_stats,
            "page": page,
            "page_size": page_size,
        },
    )
