"""
Clans API v2 - Clan Management Endpoints

This module provides v2 API endpoints for managing and retrieving clan
information in the osu! server application. It implements RESTful endpoints
for clan listing and individual clan retrieval with pagination support.

The module uses the v2 API response format with standardized success and
failure responses, providing consistent error handling and metadata
for paginated results.

Key Features:
    - Paginated clan listing with configurable page sizes
    - Individual clan retrieval by ID
    - Standardized v2 API response format
    - Type-safe response models using Pydantic
    - Integration with clan repository for data access

Integration Points:
    - Clan data access in app/repositories/clans.py
    - Response formatting in app/api/v2/common/responses.py
    - Data models in app/api/v2/models/clans.py
    - FastAPI router for endpoint registration

Endpoints:
    - GET /clans: List clans with pagination
    - GET /clans/{clan_id}: Get specific clan by ID

Usage Pattern:
    # List clans with pagination
    GET /api/v2/clans?page=1&page_size=50

    # Get specific clan
    GET /api/v2/clans/123

Related Files:
    - app/repositories/clans.py: Clan data access layer
    - app/api/v2/models/clans.py: Clan data models
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Failure, Success
from app.api.v2.models.clans import Clan
from app.repositories import clans as clans_repo

router: APIRouter = APIRouter()


@router.get("/clans")
async def get_clans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Success[list[Clan]] | Failure:
    clans = await clans_repo.fetch_many(
        page=page,
        page_size=page_size,
    )
    total_clans = await clans_repo.fetch_count()

    response = [Clan.from_mapping(rec) for rec in clans]
    return responses.success(
        content=response,
        meta={
            "total": total_clans,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/clans/{clan_id}")
async def get_clan(clan_id: int) -> Success[Clan] | Failure:
    data = await clans_repo.fetch_one(id=clan_id)
    if data is None:
        return responses.failure(
            message="Clan not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = Clan.from_mapping(data)
    return responses.success(response)
