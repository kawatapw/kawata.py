"""
API v2 Package - Modern RESTful API Endpoints

This module initializes and configures the v2 API router for the osu! server
application, providing a modern RESTful interface for accessing server data
and functionality. It aggregates all v2 API endpoint modules into a single
router with consistent routing and tagging.

The v2 API represents the modernized interface for the osu! server, offering
improved performance, better error handling, and more consistent response
formats compared to the legacy v1 API. All v2 endpoints are prefixed with
"/v2" and organized by resource type.

Key Features:
    - Modern RESTful API design principles
    - Consistent response formatting across all endpoints
    - Comprehensive error handling and validation
    - Type-safe request/response models using Pydantic
    - Modular router organization by resource type
    - Automatic OpenAPI documentation generation

Integration Points:
    - Clan management endpoints in app/api/v2/clans.py
    - Map data endpoints in app/api/v2/maps.py
    - Player information endpoints in app/api/v2/players.py
    - Score tracking endpoints in app/api/v2/scores.py
    - Client utilities in app/api/v2/client.py
    - FastAPI application in app/api/init_api.py

API Organization:
    - clans: Clan management and information
    - maps: Beatmap data and metadata
    - players: Player profiles and statistics
    - scores: Score submission and retrieval
    - client: Client-side utilities and information

Usage Pattern:
    # Access through the main API router
    from app.api import api_router
    
    # Or directly from v2 module
    from app.api.v2 import apiv2_router
    
    # Individual endpoint modules
    from app.api.v2 import clans, maps, players, scores, client

Related Files:
    - app/api/__init__.py: Main API router initialization
    - app/api/init_api.py: FastAPI application setup
    - app/api/v2/common/: Shared utilities and models
    - app/api/v2/models/: Pydantic data models
"""

# isort: dont-add-imports

from fastapi import APIRouter

from . import clans
from . import maps
from . import players
from . import scores
from . import seasons
from . import client

apiv2_router = APIRouter(tags=["API v2"], prefix="/v2")

apiv2_router.include_router(clans.router)
apiv2_router.include_router(maps.router)
apiv2_router.include_router(players.router)
apiv2_router.include_router(scores.router)
apiv2_router.include_router(seasons.router)
apiv2_router.include_router(client.router)
