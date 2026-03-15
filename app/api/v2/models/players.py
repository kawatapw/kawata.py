"""
Players Models Module - Pydantic Data Models for Player API

This module defines Pydantic data models for player-related API requests and
responses in the v2 API endpoints. It provides type-safe data structures
for player information exchange between the server and clients, ensuring
consistent data validation and serialization.

The module uses Pydantic's BaseModel for creating robust data models that
provide automatic validation, serialization, and documentation generation
for player-related API operations. These models are used by the player API
endpoints to structure request and response data.

Key Features:
    - Type-safe player data structures using Pydantic
    - Automatic data validation and serialization
    - Clear data structure definitions with type hints
    - Integration with FastAPI for request/response validation
    - Automatic documentation generation
    - Data coercion and validation error handling

Integration Points:
    - Player API endpoints in app/api/v2/players.py
    - Player data access in app/repositories/users.py
    - Statistics data access in app/repositories/stats.py
    - Database operations with validated player data
    - Client-server communication for player information

Player Models:
    - Player: Core player information and profile data
    - PlayerStatus: Current player status and activity
    - PlayerStats: Player statistics for specific game modes

Player Structure:
    - id: Unique identifier for the player
    - name: Display name of the player
    - safe_name: URL-safe version of the name
    - priv: Bitwise privilege flags
    - country: Two-letter country code
    - silence_end: Unix timestamp when silence ends
    - donor_end: Unix timestamp when donor status ends
    - creation_time: Unix timestamp when account was created
    - latest_activity: Unix timestamp of last activity
    - clan_id: Clan ID (0 if not in clan)
    - clan_priv: Clan privilege level
    - preferred_mode: Preferred game mode
    - play_style: Play style preferences
    - custom_badge_name: Custom badge name
    - custom_badge_icon: Custom badge icon URL
    - userpage_content: User profile content

PlayerStatus Structure:
    - login_time: Unix timestamp when player logged in
    - action: Current action (idle, playing, editing, etc.)
    - info_text: Additional status information
    - mode: Current game mode
    - mods: Current mods applied
    - beatmap_id: Current beatmap being played

PlayerStats Structure:
    - id: Player ID
    - mode: Game mode
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
    # Create player response data
    player_data = Player(
        id=12345,
        name="PlayerName",
        safe_name="playername",
        priv=3,
        country="US",
        silence_end=0,
        donor_end=0,
        creation_time=1640995200,
        latest_activity=1640995200,
        clan_id=0,
        clan_priv=0,
        preferred_mode=0,
        play_style=0,
        custom_badge_name=None,
        custom_badge_icon=None,
        userpage_content=None
    )
    
    # Use in API endpoint
    @router.get("/players/{player_id}")
    async def get_player(player_id: int) -> Player:
        player_data = await users_repo.fetch_one(id=player_id)
        return Player(**player_data)

Related Files:
    - app/api/v2/players.py: Player API endpoints
    - app/repositories/users.py: User data access layer
    - app/repositories/stats.py: Statistics data access layer
    - app/api/v2/common/responses.py: Response formatting utilities
"""

from __future__ import annotations

from . import BaseModel

# input models


# output models


class Player(BaseModel):
    """Pydantic model for player data in API responses.
    
    Attributes:
        id: Unique identifier for the player
        name: Display name of the player
        safe_name: URL-safe version of the name
        priv: Bitwise privilege flags
        country: Two-letter country code
        silence_end: Unix timestamp when silence ends
        donor_end: Unix timestamp when donor status ends
        creation_time: Unix timestamp when account was created
        latest_activity: Unix timestamp of last activity
        clan_id: Clan ID (0 if not in clan)
        clan_priv: Clan privilege level
        preferred_mode: Preferred game mode
        play_style: Play style preferences
        custom_badge_name: Custom badge name
        custom_badge_icon: Custom badge icon URL
        userpage_content: User profile content
    """
    id: int
    name: str
    safe_name: str

    priv: int
    country: str
    silence_end: int
    donor_end: int
    creation_time: int
    latest_activity: int

    clan_id: int
    clan_priv: int

    preferred_mode: int
    play_style: int

    custom_badge_name: str | None
    custom_badge_icon: str | None

    userpage_content: str | None


class PlayerStatus(BaseModel):
    """Pydantic model for player status data in API responses.
    
    Attributes:
        login_time: Unix timestamp when player logged in
        action: Current action (idle, playing, editing, etc.)
        info_text: Additional status information
        mode: Current game mode
        mods: Current mods applied
        beatmap_id: Current beatmap being played
    """
    login_time: int
    action: int
    info_text: str
    mode: int
    mods: int
    beatmap_id: int


class PlayerStats(BaseModel):
    """Pydantic model for player statistics data in API responses.
    
    Attributes:
        id: Player ID
        mode: Game mode
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
    tscore: int
    rscore: int
    pp: float
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
