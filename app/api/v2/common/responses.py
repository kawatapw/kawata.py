"""
Responses Module - Standardized API Response Formatting

This module provides standardized response formatting utilities for the v2 API
endpoints in the osu! server application. It implements consistent response
structures for both successful operations and error conditions, ensuring
uniform API behavior across all endpoints.

The module uses Pydantic models for type-safe response structures and integrates
with the custom JSON serialization utilities for high-performance response
handling. It provides generic success responses with metadata support and
standardized error responses with clear error messages.

Key Features:
    - Standardized success response structure with metadata
    - Consistent error response format with error messages
    - Generic type support for flexible data handling
    - Integration with custom JSON serialization
    - Type-safe response models using Pydantic
    - HTTP status code support for proper HTTP semantics

Integration Points:
    - JSON serialization in app/api/v2/common/json.py
    - API endpoints throughout v2 API
    - Pydantic models in app/api/v2/models/
    - FastAPI response handling

Response Structures:
    - Success: {"status": "success", "data": <content>, "meta": <metadata>}
    - Failure: {"status": "error", "error": <error_message>}

Usage Pattern:
    # Return success response with data
    from app.api.v2.common.responses import success

    return success(
        content={"key": "value"},
        status_code=200,
        meta={"total": 100, "page": 1}
    )

    # Return error response
    from app.api.v2.common.responses import failure

    return failure(
        message="Resource not found",
        status_code=404
    )

Related Files:
    - app/api/v2/common/json.py: JSON serialization utilities
    - app/api/v2/models/: Pydantic data models
    - app/api/v2/*.py: API endpoints using response utilities
"""

from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar, cast

from pydantic import BaseModel

from app.api.v2.common import json

T = TypeVar("T")


class Success(BaseModel, Generic[T]):
    status: Literal["success"]
    data: T
    meta: dict[str, Any]


def success(
    content: T,
    status_code: int = 200,
    headers: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> Success[T]:
    if meta is None:
        meta = {}
    data = {"status": "success", "data": content, "meta": meta}
    # XXX:HACK to make typing work
    return cast(Success[T], json.ORJSONResponse(data, status_code, headers))


class Failure(BaseModel):
    status: Literal["error"]
    error: str


def failure(
    message: str,
    status_code: int = 400,
    headers: dict[str, Any] | None = None,
) -> Failure:
    data = {"status": "error", "error": message}
    # XXX:HACK to make typing work
    return cast(Failure, json.ORJSONResponse(data, status_code, headers))
