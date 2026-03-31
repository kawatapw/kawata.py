"""
Client API v2 - Client-Specific Data Endpoints

This module provides v2 API endpoints for retrieving client-specific data
in the osu! server application. It implements RESTful endpoints for accessing
changelog information with advanced filtering and pagination capabilities.

The module uses the v2 API response format with standardized success and
failure responses, providing consistent error handling and metadata
for paginated results. It supports filtering by change type, category,
and time range for flexible changelog queries.

Key Features:
    - Paginated changelog listing with configurable page sizes
    - Filtering by change type (0-2)
    - Category-based filtering
    - Time-based filtering with Unix timestamp support
    - Standardized v2 API response format
    - Type-safe response models using Pydantic
    - Integration with database for data access

Integration Points:
    - Database access in app/state/services.py
    - Response formatting in app/api/v2/common/responses.py
    - Logging in app/logging.py
    - FastAPI router for endpoint registration

Endpoints:
    - GET /changelog: List changelog entries with filtering and pagination

Usage Pattern:
    # List changelog with pagination
    GET /api/v2/changelog?page=1&page_size=50

    # Filter by change type
    GET /api/v2/changelog?change_type=1

    # Filter by category
    GET /api/v2/changelog?category=feature

    # Filter by time range
    GET /api/v2/changelog?unix_from=1640995200

Related Files:
    - app/state/services.py: Database connection management
    - app/api/v2/common/responses.py: Response formatting utilities
    - app/logging.py: Logging utilities
"""

from __future__ import annotations

import textwrap
from typing import Any

from fastapi import APIRouter, status
from fastapi.param_functions import Query

from app.api.v2.common import responses
from app.api.v2.common.responses import Failure, Success
from app.logging import log
from app.state.services import database

router: APIRouter = APIRouter()

READ_PARAMS = textwrap.dedent(
    """\
        type, category, poster, content, time, version
    """,
)


@router.get("/changelog")
async def get_changelog(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    change_type: int | None = Query(None, ge=0, le=2),
    category: str | None = None,
    unix_from: int = 0,
) -> Success[list[dict[str, Any]]] | Failure:
    try:
        params: dict[str, Any] = {}
        query = rf"""\
            SELECT {READ_PARAMS}
              FROM changelog
            """  # nosec B608
        accessor = "WHERE"  # used to add ANDs to the query

        if change_type is not None:
            query += accessor + " type = :type "
            accessor = "AND"
            params["type"] = change_type

        if category is not None:
            query += accessor + " category = :category "
            accessor = "AND"
            params["category"] = category

        query += accessor + " UNIX_TIMESTAMP(time) >= :unix_from "

        query += """
                LIMIT :limit
                OFFSET :offset
            """
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        params["unix_from"] = unix_from

        data = await database.fetch_all(query, params)
        if data is None:
            return responses.failure(
                message="An error occurred while fetching changelog.",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Build count query with same filters (excluding LIMIT/OFFSET)
        count_query = "SELECT COUNT(*) AS cnt FROM changelog "
        count_accessor = "WHERE"
        count_params: dict[str, Any] = {}
        if change_type is not None:
            count_query += count_accessor + " type = :type "
            count_accessor = "AND"
            count_params["type"] = change_type
        if category is not None:
            count_query += count_accessor + " category = :category "
            count_accessor = "AND"
            count_params["category"] = category
        count_query += count_accessor + " UNIX_TIMESTAMP(time) >= :unix_from "
        count_params["unix_from"] = unix_from
        total_row = await database.fetch_val(count_query, count_params)

        meta = {
            "total": total_row or len(data),
            "page": page,
            "page_size": page_size,
            "type": change_type,
            "category": category,
            "unix_from": unix_from,
        }
        res = []
        for row in data:
            res.append(
                {
                    "type": row["type"],
                    "category": row["category"],
                    "poster": row["poster"],
                    "content": row["content"],
                    "time": row["time"].strftime("%Y-%m-%d %H:%M:%S"),
                    "version": row["version"],
                },
            )
        return responses.success(content=res, meta=meta)
    except Exception as e:
        log(f"Error in get_changelog: {e}")
        return responses.failure(
            message="An error occurred while fetching changelog.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
