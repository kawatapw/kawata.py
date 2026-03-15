"""
Maps API v2 - Beatmap Management Endpoints

This module provides v2 API endpoints for managing and retrieving beatmap
information in the osu! server application. It implements RESTful endpoints
for beatmap listing and individual beatmap retrieval with comprehensive
filtering and pagination support.

The module uses the v2 API response format with standardized success and
failure responses, providing consistent error handling and metadata
for paginated results. It supports filtering by various beatmap attributes
including server, status, artist, creator, and game mode.

Key Features:
    - Paginated beatmap listing with configurable page sizes
    - Comprehensive filtering by multiple beatmap attributes
    - Individual beatmap retrieval by ID
    - Standardized v2 API response format
    - Type-safe response models using Pydantic
    - Integration with beatmap repository for data access

Integration Points:
    - Beatmap data access in app/repositories/maps.py
    - Response formatting in app/api/v2/common/responses.py
    - Data models in app/api/v2/models/maps.py
    - FastAPI router for endpoint registration

Endpoints:
    - GET /maps: List beatmaps with filtering and pagination
    - GET /maps/{map_id}: Get specific beatmap by ID

Filtering Options:
    - set_id: Filter by beatmap set ID
    - server: Filter by server type (osu!, private)
    - status: Filter by ranked status
    - artist: Filter by artist name
    - creator: Filter by creator name
    - filename: Filter by filename
    - mode: Filter by game mode
    - frozen: Filter by frozen status

Usage Pattern:
    # List beatmaps with pagination
    GET /api/v2/maps?page=1&page_size=50
    
    # Filter by server and status
    GET /api/v2/maps?server=osu!&status=2
    
    # Filter by artist and mode
    GET /api/v2/maps?artist=ArtistName&mode=0
    
    # Get specific beatmap
    GET /api/v2/maps/12345

Related Files:
    - app/repositories/maps.py: Beatmap data access layer
    - app/api/v2/models/maps.py: Beatmap data models
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.maps import Map
from app.repositories import maps as maps_repo

router = APIRouter()


@router.get("/maps")
async def get_maps(
    set_id: int | None = None,
    server: str | None = None,
    status: int | None = None,
    artist: str | None = None,
    creator: str | None = None,
    filename: str | None = None,
    mode: int | None = None,
    frozen: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Map]] | Failure:
    maps = await maps_repo.fetch_many(
        server=server,
        set_id=set_id,
        status=status,
        artist=artist,
        creator=creator,
        filename=filename,
        mode=mode,
        frozen=frozen,
        page=page,
        page_size=page_size,
    )
    total_maps = await maps_repo.fetch_count(
        server=server,
        set_id=set_id,
        status=status,
        artist=artist,
        creator=creator,
        filename=filename,
        mode=mode,
        frozen=frozen,
    )

    response = [Map.from_mapping(rec) for rec in maps]

    return responses.success(
        content=response,
        meta={
            "total": total_maps,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/maps/{map_id}")
async def get_map(map_id: int) -> Success[Map] | Failure:
    data = await maps_repo.fetch_one(id=map_id)
    if data is None:
        return responses.failure(
            message="Map not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Map.from_mapping(data)
    return responses.success(response)
