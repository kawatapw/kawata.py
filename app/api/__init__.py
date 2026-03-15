"""
API Package Initialization - FastAPI Router Configuration

This module initializes the main API router for the osu! server application,
combining all API versions and domain-specific routers into a unified routing
system. It serves as the central configuration point for all HTTP API endpoints,
organizing them by version and domain for maintainability and scalability.

The module creates the main APIRouter instance that aggregates all sub-routers
from different API versions (v1, v2) and domain-specific modules, providing
a single entry point for all HTTP API functionality in the application.

Key Features:
    - Centralized API router configuration
    - Version-based API organization (v1, v2)
    - Domain-specific router aggregation
    - Modular router composition
    - Clean separation of API concerns
    - Scalable routing architecture

Integration Points:
    - API v1 endpoints in app/api/v1/
    - API v2 endpoints in app/api/v2/
    - Domain-specific endpoints in app/api/domains/
    - Application initialization in app/api/init_api.py
    - Middleware configuration in app/api/middlewares.py

Router Organization:
    - api_router: Main router aggregating all sub-routers
    - apiv1_router: Legacy API endpoints (v1)
    - apiv2_router: Modern API endpoints (v2)
    - domains: Domain-specific routers (cho, osu, map, packets)

Usage Pattern:
    # The main router is used in the FastAPI application
    from app.api import api_router
    
    # Include in FastAPI app
    app.include_router(api_router)
    
    # Access sub-routers
    from app.api.v1 import apiv1_router
    from app.api.v2 import apiv2_router

Related Files:
    - app/api/v1/__init__.py: API v1 router initialization
    - app/api/v2/__init__.py: API v2 router initialization
    - app/api/domains/: Domain-specific routers
    - app/api/init_api.py: FastAPI application setup
    - app/api/middlewares.py: HTTP middleware configuration
"""

# type: ignore
# isort: dont-add-imports

from fastapi import APIRouter

from .v1 import apiv1_router
from .v2 import apiv2_router

api_router = APIRouter()

api_router.include_router(apiv1_router)
api_router.include_router(apiv2_router)

from . import domains
from . import init_api
from . import middlewares
