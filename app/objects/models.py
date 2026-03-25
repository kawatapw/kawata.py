"""
Models Module - Pydantic Data Models for Request Validation

This module defines Pydantic data models used for validating and serializing
request data in the osu! server application. These models provide type-safe
data structures with automatic validation, serialization, and documentation
generation for API endpoints and internal data processing.

The module uses Pydantic's BaseModel for creating robust data models that
ensure data integrity and provide clear interfaces for data exchange between
different parts of the application. These models are particularly useful for
validating incoming request data and ensuring consistent data structures.

Key Features:
    - Type-safe data validation using Pydantic
    - Automatic data serialization and deserialization
    - Clear data structure definitions with type hints
    - Integration with FastAPI for request/response validation
    - Automatic documentation generation
    - Data coercion and validation error handling

Integration Points:
    - API endpoint validation in app/api/v2/
    - Request processing in app/api/domains/
    - Data serialization for database operations
    - Client-server communication protocols
    - Internal data transfer between application layers

Usage Pattern:
    - Models are used to validate incoming request data
    - They provide clear interfaces for data structures
    - Automatic validation ensures data integrity
    - Serialization handles data conversion between formats
    - Type hints enable better IDE support and documentation

Example Usage:
    # Validate beatmap request data
    request_data = {
        "Filenames": ["beatmap1.osu", "beatmap2.osu"],
        "Ids": [12345, 67890]
    }

    form = OsuBeatmapRequestForm(**request_data)
    filenames = form.Filenames  # ["beatmap1.osu", "beatmap2.osu"]
    ids = form.Ids  # [12345, 67890]

Related Files:
    - app/api/v2/: API endpoints using these models
    - app/api/domains/: Domain-specific request handling
    - app/repositories/: Database operations with validated data
"""

from __future__ import annotations

from pydantic import BaseModel


class OsuBeatmapRequestForm(BaseModel):
    Filenames: list[str]
    Ids: list[int]
