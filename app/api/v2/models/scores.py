"""
Scores Models Module - Pydantic Data Models for Score API

This module defines Pydantic data models for score-related API requests and
responses in the v2 API endpoints. It provides type-safe data structures
for score information exchange between the server and clients, ensuring
consistent data validation and serialization.

The module uses Pydantic's BaseModel for creating robust data models that
provide automatic validation, serialization, and documentation generation
for score-related API operations. These models are used by the score API
endpoints to structure request and response data.

Key Features:
    - Type-safe score data structures using Pydantic
    - Automatic data validation and serialization
    - Clear data structure definitions with type hints
    - Integration with FastAPI for request/response validation
    - Automatic documentation generation
    - Data coercion and validation error handling

Integration Points:
    - Score API endpoints in app/api/v2/scores.py
    - Score data access in app/repositories/scores.py
    - Database operations with validated score data
    - Client-server communication for score information

Score Structure:
    - id: Unique identifier for the score
    - map_md5: Beatmap MD5 hash
    - userid: Player ID who set the score
    - score: Total score value
    - pp: Performance points earned
    - acc: Accuracy percentage
    - max_combo: Maximum combo achieved
    - mods: Bitwise mods applied
    - n300, n100, n50, nmiss, ngeki, nkatu: Hit counts
    - grade: Letter grade (N, F, D, C, B, A, S, SH, X, XH)
    - status: Submission status (failed, submitted, best)
    - mode: Game mode (osu!, taiko, catch, mania)
    - play_time: When the score was played
    - time_elapsed: Time taken to complete the map
    - perfect: Whether the score is a full combo

Usage Pattern:
    # Create score response data
    score_data = Score(
        id=12345,
        map_md5="abc123...",
        userid=67890,
        score=1000000,
        pp=100.5,
        acc=95.5,
        max_combo=500,
        mods=0,
        n300=300,
        n100=50,
        n50=10,
        nmiss=5,
        ngeki=0,
        nkatu=0,
        grade="A",
        status=2,
        mode=0,
        play_time=datetime.now(),
        time_elapsed=180,
        perfect=False
    )

    # Use in API endpoint
    @router.get("/scores/{score_id}")
    async def get_score(score_id: int) -> Score:
        score_data = await scores_repo.fetch_one(id=score_id)
        return Score(**score_data)

Related Files:
    - app/api/v2/scores.py: Score API endpoints
    - app/repositories/scores.py: Score data access layer
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from datetime import datetime

from . import BaseModel
from .seasons import SeasonInfo

# input models


# output models


class Score(BaseModel):
    """Pydantic model for score data in API responses.

    Attributes:
        id: Unique identifier for the score
        map_md5: Beatmap MD5 hash
        userid: Player ID who set the score
        score: Total score value
        pp: Performance points earned
        acc: Accuracy percentage
        max_combo: Maximum combo achieved
        mods: Bitwise mods applied
        n300: Number of 300s hit
        n100: Number of 100s hit
        n50: Number of 50s hit
        nmiss: Number of misses
        ngeki: Number of gekis (mania)
        nkatu: Number of katus (mania)
        grade: Letter grade (N, F, D, C, B, A, S, SH, X, XH)
        status: Submission status (failed, submitted, best)
        mode: Game mode (osu!, taiko, catch, mania)
        play_time: When the score was played
        time_elapsed: Time taken to complete the map
        perfect: Whether the score is a full combo
        season: Season information (if seasons enabled)
    """

    id: int
    map_md5: str
    userid: int

    score: int
    pp: float
    acc: float
    max_combo: int
    mods: int

    n300: int
    n100: int
    n50: int
    nmiss: int
    ngeki: int
    nkatu: int

    grade: str
    status: int
    mode: int

    play_time: datetime
    time_elapsed: int
    perfect: bool
