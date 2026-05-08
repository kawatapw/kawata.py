"""
State Package - Global Application State Management

This module serves as the central state management hub for the osu! server
application, providing global variables and state containers that are shared
across all application components. It initializes and manages the application's
runtime state including the event loop, packet handlers, and various caches.

The module acts as a singleton state container, ensuring that all parts of
the application have access to consistent global state. It coordinates the
initialization of sub-modules (cache, services, sessions) and provides
global variables that are used throughout the application lifecycle.

Key Features:
    - Global event loop management
    - Packet handler registry for all client packets
    - Score submission lock management for concurrent access
    - Shutdown state tracking for graceful termination
    - Sub-module initialization and coordination
    - Type-safe global state containers

Integration Points:
    - Cache management in app/state/cache.py
    - Service initialization in app/state/services.py
    - Session management in app/state/sessions.py
    - Packet handling in app/packets.py
    - Event loop management throughout the application

Global State Variables:
    - loop: The main asyncio event loop for the application
    - score_submission_locks: Per-user locks for concurrent score submissions
    - packets: Registry of packet handlers for all and restricted packets
    - shutting_down: Flag indicating graceful shutdown in progress

Usage Pattern:
    # Access global event loop
    from app.state import loop

    # Access packet handlers
    from app.state import packets
    handler = packets["all"][packet_type]

    # Use score submission locks
    from app.state import score_submission_locks
    async with score_submission_locks[user_id]:
        # Process score submission

    # Check shutdown state
    from app.state import shutting_down
    if shutting_down:
        # Handle graceful shutdown

Related Files:
    - app/state/cache.py: Application caching system
    - app/state/services.py: Service initialization and management
    - app/state/sessions.py: Session and connection management
    - app/packets.py: Packet definitions and handlers
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from . import cache, services, sessions

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from app.adapters.database import Database
    from app.packets import BasePacket, ClientPackets

loop: AbstractEventLoop | None = None
score_submission_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
packets: dict[Literal["all", "restricted"], dict[ClientPackets, type[BasePacket]]] = {
    "all": {},
    "restricted": {},
}
shutting_down = False


@dataclass
class State:
    """Application state container for dependency injection."""

    sessions: Any  # sessions module with players, channels, etc.
    services: Any  # services module with database, http_client, etc.
    cache: Any  # cache module
    database: Database | None = None
    loop: Any = None  # event loop for scheduling
    usecases: Any = None  # usecases module for business logic


# Create a global state instance for dependency injection
state = State(
    sessions=sessions,
    services=services,
    cache=cache,
)

__all__ = [
    "cache",
    "services",
    "sessions",
    "loop",
    "score_submission_locks",
    "packets",
    "shutting_down",
    "State",
    "state",
]
