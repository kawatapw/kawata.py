"""
Seasons Models Module - Pydantic Data Models for Seasons API

This module defines Pydantic data models for season-related API requests and
responses in the v2 API endpoints. It provides type-safe data structures
for season information exchange between the server and clients, ensuring
consistent data validation and serialization.

The module uses Pydantic's BaseModel for creating robust data models that
provide automatic validation, serialization, and documentation generation
for season-related API operations. These models are used by the seasons API
endpoints to structure request and response data.

Key Features:
    - Type-safe season data structures using Pydantic
    - Automatic data validation and serialization
    - Clear data structure definitions with type hints
    - Integration with FastAPI for request/response validation
    - Automatic documentation generation
    - Data coercion and validation error handling

Integration Points:
    - Seasons API endpoints in app/api/v2/seasons.py
    - Seasons data access in app/repositories/seasons.py
    - Statistics data access in app/repositories/stats.py
    - Database operations with validated season data
    - Client-server communication for season information

Season Models:
    - Season: Core season information and metadata
    - SeasonStats: Season statistics for specific game modes
    - SeasonInfo: Minimal season information for embedding in other responses

Season Structure:
    - id: Unique identifier for the season
    - name: Display name of the season
    - schedule_id: ID of the schedule this season belongs to
    - start_date: When the season starts
    - end_date: When the season ends
    - is_active: Whether the season is currently active
    - end_calculated: Whether final stats have been calculated
    - awards_badges: Whether this season awards badges
    - description: Optional description of the season
    - created_at: When the season was created

SeasonStats Structure:
    - id: Player ID
    - mode: Game mode
    - season_id: Season ID
    - tscore: Total score
    - rscore: Ranked score
    - pp: Performance points
    - plays: Total play count
    - playtime: Total playtime in seconds
    - acc: Average accuracy
    - max_combo: Maximum combo achieved
    - total_hits: Total number of hits
    - replay_views: Number of replay views
    - xh_count, x_count, sh_count, s_count, a_count: Grade counts

Usage Pattern:
    # Create season response data
    season_data = Season(
        id=1,
        name="Spring 2024",
        schedule_id=1,
        start_date=datetime(2024, 3, 20),
        end_date=datetime(2024, 6, 20),
        is_active=True,
        end_calculated=False,
        awards_badges=False,
        description="Spring season 2024",
        created_at=datetime.now()
    )

    # Use in API endpoint
    @router.get("/seasons/{season_id}")
    async def get_season(season_id: int) -> Season:
        season_data = await seasons_repo.fetch_one(id=season_id)
        return Season(**season_data)

Related Files:
    - app/api/v2/seasons.py: Seasons API endpoints
    - app/repositories/seasons.py: Seasons data access layer
    - app/repositories/stats.py: Statistics data access layer
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from datetime import datetime

from . import BaseModel


class Season(BaseModel):
    """Pydantic model for season data in API responses.

    Attributes:
        id: Unique identifier for the season
        name: Display name of the season
        schedule_id: ID of the schedule this season belongs to
        start_date: When the season starts
        end_date: When the season ends
        is_active: Whether the season is currently active
        end_calculated: Whether final stats have been calculated
        awards_badges: Whether this season awards badges
        description: Optional description of the season
        created_at: When the season was created
    """

    id: int
    name: str
    schedule_id: int | None
    start_date: datetime
    end_date: datetime
    is_active: bool
    end_calculated: bool
    awards_badges: bool
    description: str | None
    created_at: datetime


class SeasonStats(BaseModel):
    """Pydantic model for season statistics data in API responses.

    Attributes:
        id: Player ID
        mode: Game mode
        season_id: Season ID
        tscore: Total score
        rscore: Ranked score
        pp: Performance points
        plays: Total play count
        playtime: Total playtime in seconds
        acc: Average accuracy
        max_combo: Maximum combo achieved
        total_hits: Total number of hits
        replay_views: Number of replay views
        xh_count: Number of XH (SS with Hidden) grades
        x_count: Number of X (SS) grades
        sh_count: Number of SH (S with Hidden) grades
        s_count: Number of S grades
        a_count: Number of A grades
    """

    id: int
    mode: int
    season_id: int | None
    tscore: int
    rscore: int
    pp: int
    plays: int
    playtime: int
    acc: float
    max_combo: int
    total_hits: int
    replay_views: int
    xh_count: int
    x_count: int
    sh_count: int
    s_count: int
    a_count: int


class SeasonInfo(BaseModel):
    """Pydantic model for minimal season information (for embedding in other responses).

    Attributes:
        id: Unique identifier for the season
        name: Display name of the season
        type: Schedule type identifier
        start_date: When the season starts
        end_date: When the season ends
    """

    id: int
    name: str
    type: str
    start_date: datetime
    end_date: datetime
