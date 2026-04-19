"""
Clans Models Module - Pydantic Data Models for Clan API

This module defines Pydantic data models for clan-related API requests and
responses in the v2 API endpoints. It provides type-safe data structures
for clan information exchange between the server and clients, ensuring
consistent data validation and serialization.

The module uses Pydantic's BaseModel for creating robust data models that
provide automatic validation, serialization, and documentation generation
for clan-related API operations. These models are used by the clan API
endpoints to structure request and response data.

Key Features:
    - Type-safe clan data structures using Pydantic
    - Automatic data validation and serialization
    - Clear data structure definitions with type hints
    - Integration with FastAPI for request/response validation
    - Automatic documentation generation
    - Data coercion and validation error handling

Integration Points:
    - Clan API endpoints in app/api/v2/clans.py
    - Clan data access in app/repositories/clans.py
    - Database operations with validated clan data
    - Client-server communication for clan information

Clan Structure:
    - id: Unique identifier for the clan
    - name: Display name of the clan
    - tag: Short tag for clan identification
    - owner: Player ID of the clan owner
    - created_at: Timestamp when the clan was created

Usage Pattern:
    # Create clan response data
    clan_data = Clan(
        id=1,
        name="My Clan",
        tag="MC",
        owner=12345,
        created_at=datetime.now()
    )

    # Use in API endpoint
    @router.get("/clans/{clan_id}")
    async def get_clan(clan_id: int) -> Clan:
        clan_data = await clans_repo.fetch_one(id=clan_id)
        return Clan(**clan_data)

Related Files:
    - app/api/v2/clans.py: Clan API endpoints
    - app/repositories/clans.py: Clan data access layer
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from datetime import datetime

from . import BaseModel

# input models


# output models


class Clan(BaseModel):
    """Pydantic model for clan data in API responses.

    Attributes:
        id: Unique identifier for the clan
        name: Display name of the clan
        tag: Short tag for clan identification
        owner: Player ID of the clan owner
        created_at: Timestamp when the clan was created
    """

    id: int
    name: str
    tag: str
    owner: int
    created_at: datetime
