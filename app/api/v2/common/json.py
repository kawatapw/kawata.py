"""
JSON Utilities Module - FastAPI JSON Response Handling

This module provides JSON serialization utilities for the v2 API endpoints
in the osu! server application. It implements custom JSON response handling
using orjson for high-performance serialization and supports Pydantic models
for automatic data conversion.

The module provides a custom FastAPI response class that uses orjson for
JSON serialization, offering better performance than the standard json module.
It includes automatic handling of Pydantic BaseModel objects for seamless
integration with the API's data models.

Key Features:
    - High-performance JSON serialization using orjson
    - Automatic Pydantic BaseModel to dict conversion
    - Recursive processing of nested data structures
    - Custom FastAPI JSONResponse implementation
    - Type-safe data handling with proper type hints

Integration Points:
    - FastAPI response handling in app/api/v2/
    - Pydantic models in app/api/v2/models/
    - API endpoint responses throughout v2 API
    - Data serialization for client communication

Usage Pattern:
    # Use custom JSON response in endpoints
    from app.api.v2.common.json import ORJSONResponse
    
    @router.get("/endpoint")
    async def endpoint() -> ORJSONResponse:
        data = {"key": "value"}
        return ORJSONResponse(content=data)
    
    # Direct JSON serialization
    from app.api.v2.common.json import dumps
    
    json_bytes = dumps({"key": "value"})

Related Files:
    - app/api/v2/common/responses.py: Response formatting utilities
    - app/api/v2/models/: Pydantic data models
    - app/api/v2/*.py: API endpoints using JSON responses
"""

from __future__ import annotations

from typing import Any

import orjson
from fastapi.responses import JSONResponse
from pydantic import BaseModel


def _default_processor(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return _default_processor(data.dict())
    elif isinstance(data, dict):
        return {k: _default_processor(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_default_processor(v) for v in data]
    else:
        return data


def dumps(data: Any) -> bytes:
    return orjson.dumps(data, default=_default_processor)


class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return dumps(content)
