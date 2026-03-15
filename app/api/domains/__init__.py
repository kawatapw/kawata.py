"""
API Domains Package - Domain-Specific API Endpoints

This module serves as the central hub for all domain-specific API endpoints
in the osu! server application. It imports and exposes all domain routers,
providing a unified interface for accessing different API domains including
cho protocol handling, map management, osu! web API compatibility, and
packet processing modules.

The package organizes API endpoints by domain, each handling specific
aspects of the osu! server functionality. This includes the CHO protocol
for client communication, map-related endpoints, osu! web API compatibility,
and specialized packet handlers for different client types.

Key Features:
    - Centralized access to all domain-specific API endpoints
    - Modular organization of API functionality
    - Clean separation of concerns by domain
    - Type-safe router composition
    - Integration with FastAPI routing system

Integration Points:
    - CHO protocol handling in app/api/domains/cho.py
    - Map management in app/api/domains/map.py
    - osu! web API in app/api/domains/osu.py
    - Common packet utilities in app/api/domains/packets/common.py
    - Aeris packet handlers in app/api/domains/packets/aeris.py
    - FastAPI application in app/api/init_api.py

Domain Organization:
    - cho: CHO protocol endpoints for client communication
    - map: Map-related endpoints and utilities
    - osu: osu! web API compatibility endpoints
    - packets/common: Common packet handling utilities
    - packets/aeris: Aeris-specific packet handlers

Usage Pattern:
    # Import domain routers
    from app.api.domains import cho, map, osu
    
    # Import packet utilities
    from app.api.domains.packets import common, aeris
    
    # Access through package
    import app.api.domains
    router = app.api.domains.cho.router

Related Files:
    - app/api/__init__.py: Main API router initialization
    - app/api/init_api.py: FastAPI application setup
    - app/api/domains/cho.py: CHO protocol endpoints
    - app/api/domains/map.py: Map domain endpoints
    - app/api/domains/osu.py: osu! web API endpoints
"""

# isort: dont-add-imports

from . import cho
from . import map
from . import osu
from .packets import common
from .packets import aeris as aeris_packets