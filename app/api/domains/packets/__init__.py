"""
Packets Domain Package - Packet Handling and Processing

This module serves as the central hub for all packet-related functionality
in the osu! server application. It imports and exposes packet handling modules
for different client types, providing a unified interface for processing
network packets from osu! clients and specialized clients like Aeris.

The package organizes packet handlers by client type and functionality,
enabling the server to process different packet formats and protocols
used by various osu! client implementations. This includes standard
osu! client packets and specialized packets from custom clients.

Key Features:
    - Centralized packet handling for all client types
    - Modular organization of packet processors
    - Support for standard osu! client packets
    - Specialized handling for Aeris client packets
    - Common packet utilities and helpers
    - Clean separation of packet processing logic

Integration Points:
    - Common packet utilities in app/api/domains/packets/common.py
    - Aeris packet handlers in app/api/domains/packets/aeris.py
    - Main API router in app/api/domains/__init__.py
    - Packet definitions in app/packets.py
    - Client communication in app/api/domains/cho.py

Module Organization:
    - common: Shared packet utilities and base classes
    - aeris: Specialized packet handlers for Aeris client

Usage Pattern:
    # Import packet modules
    from app.api.domains.packets import common, aeris
    
    # Use common packet utilities
    from app.api.domains.packets.common import PacketHandler
    
    # Access Aeris-specific handlers
    from app.api.domains.packets.aeris import AerisPacketHandler

Related Files:
    - app/api/domains/__init__.py: Domain router initialization
    - app/api/domains/cho.py: CHO protocol handling
    - app/packets.py: Packet definitions and utilities
    - app/api/domains/packets/common.py: Common packet utilities
    - app/api/domains/packets/aeris.py: Aeris packet handlers
"""

# isort: dont-add-imports

from . import common
from . import aeris