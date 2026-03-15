"""
Maps Models Module - Pydantic Data Models for Beatmap API

This module defines Pydantic data models for beatmap-related API requests and
responses in the v2 API endpoints. It provides type-safe data structures
for beatmap information exchange between the server and clients, ensuring
consistent data validation and serialization.

The module uses Pydantic's BaseModel for creating robust data models that
provide automatic validation, serialization, and documentation generation
for beatmap-related API operations. These models are used by the map API
endpoints to structure request and response data.

Key Features:
    - Type-safe beatmap data structures using Pydantic
    - Automatic data validation and serialization
    - Clear data structure definitions with type hints
    - Integration with FastAPI for request/response validation
    - Automatic documentation generation
    - Data coercion and validation error handling

Integration Points:
    - Map API endpoints in app/api/v2/maps.py
    - Beatmap data access in app/repositories/maps.py
    - Database operations with validated beatmap data
    - Client-server communication for beatmap information

Beatmap Structure:
    - id: Unique identifier for the beatmap
    - server: Server type (osu!, private)
    - set_id: Parent beatmap set identifier
    - status: Ranked status (Pending, Ranked, Approved, etc.)
    - md5: File hash for integrity verification
    - artist, title, version, creator: Metadata strings
    - filename: Original .osu filename
    - last_update: Timestamp of last modification
    - total_length: Duration in seconds
    - max_combo: Maximum possible combo
    - frozen: Whether status should be preserved during updates
    - plays, passes: Play statistics
    - mode: Game mode (osu!, taiko, catch, mania)
    - bpm, cs, od, ar, hp, diff: Difficulty attributes

Usage Pattern:
    # Create beatmap response data
    map_data = Map(
        id=12345,
        server="osu!",
        set_id=67890,
        status=2,
        md5="abc123...",
        artist="Artist",
        title="Title",
        version="Hard",
        creator="Creator",
        filename="Artist - Title (Creator) [Hard].osu",
        last_update=datetime.now(),
        total_length=180,
        max_combo=500,
        frozen=False,
        plays=1000,
        passes=500,
        mode=0,
        bpm=180.0,
        cs=4.0,
        od=8.0,
        ar=9.0,
        hp=6.0,
        diff=5.5
    )
    
    # Use in API endpoint
    @router.get("/maps/{map_id}")
    async def get_map(map_id: int) -> Map:
        map_data = await maps_repo.fetch_one(id=map_id)
        return Map(**map_data)

Related Files:
    - app/api/v2/maps.py: Map API endpoints
    - app/repositories/maps.py: Beatmap data access layer
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from datetime import datetime

from . import BaseModel

# input models


# output models


class Map(BaseModel):
    """Pydantic model for beatmap data in API responses.
    
    Attributes:
        id: Unique identifier for the beatmap
        server: Server type (osu!, private)
        set_id: Parent beatmap set identifier
        status: Ranked status (Pending, Ranked, Approved, etc.)
        md5: File hash for integrity verification
        artist: Artist name
        title: Song title
        version: Difficulty version name
        creator: Beatmap creator name
        filename: Original .osu filename
        last_update: Timestamp of last modification
        total_length: Duration in seconds
        max_combo: Maximum possible combo
        frozen: Whether status should be preserved during updates
        plays: Total play count
        passes: Total pass count
        mode: Game mode (osu!, taiko, catch, mania)
        bpm: Beats per minute
        cs: Circle size
        ar: Approach rate
        od: Overall difficulty
        hp: HP drain rate
        diff: Star difficulty rating
    """
    id: int
    server: str
    set_id: int
    status: int
    md5: str
    artist: str
    title: str
    version: str
    creator: str
    filename: str
    last_update: datetime
    total_length: int
    max_combo: int
    frozen: bool
    plays: int
    passes: int
    mode: int
    bpm: float
    cs: float
    ar: float
    od: float
    hp: float
    diff: float
