"""
Scores API v2 - Score Management and Retrieval Endpoints

This module provides v2 API endpoints for managing and retrieving score
information in the osu! server application. It implements RESTful endpoints
for score listing and individual score retrieval with comprehensive filtering
and pagination support.

The module uses the v2 API response format with standardized success and
failure responses, providing consistent error handling and metadata
for paginated results. It supports filtering by various score attributes
including beatmap, mods, status, game mode, and player.

Key Features:
    - Paginated score listing with configurable page sizes
    - Comprehensive filtering by multiple score attributes
    - Individual score retrieval by ID
    - Standardized v2 API response format
    - Type-safe response models using Pydantic
    - Integration with score repository for data access

Integration Points:
    - Score data access in app/repositories/scores.py
    - Response formatting in app/api/v2/common/responses.py
    - Data models in app/api/v2/models/scores.py
    - FastAPI router for endpoint registration

Endpoints:
    - GET /scores: List scores with filtering and pagination
    - GET /scores/{score_id}: Get specific score by ID

Filtering Options:
    - map_md5: Filter by beatmap MD5 hash
    - mods: Filter by mods applied
    - status: Filter by submission status
    - mode: Filter by game mode
    - user_id: Filter by player ID

Usage Pattern:
    # List scores with pagination
    GET /api/v2/scores?page=1&page_size=50
    
    # Filter by beatmap and mods
    GET /api/v2/scores?map_md5=abc123&mods=0
    
    # Filter by player and mode
    GET /api/v2/scores?user_id=12345&mode=0
    
    # Get specific score
    GET /api/v2/scores/67890

Related Files:
    - app/repositories/scores.py: Score data access layer
    - app/api/v2/models/scores.py: Score data models
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.scores import Score
from app.repositories import scores as scores_repo

router: APIRouter = APIRouter()


@router.get("/scores")
async def get_all_scores(
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Score]] | Failure:
    scores = await scores_repo.fetch_many(
        map_md5=map_md5,
        mods=mods,
        status=status,
        mode=mode,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    total_scores = await scores_repo.fetch_count(
        map_md5=map_md5,
        mods=mods,
        status=status,
        mode=mode,
        user_id=user_id,
    )

    response = [Score.from_mapping(rec) for rec in scores]

    return responses.success(
        content=response,
        meta={
            "total": total_scores,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/scores/{score_id}")
async def get_score(score_id: int) -> Success[Score] | Failure:
    data = await scores_repo.fetch_one(id=score_id)
    if data is None:
        return responses.failure(
            message="Score not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Score.from_mapping(data)
    return responses.success(response)
