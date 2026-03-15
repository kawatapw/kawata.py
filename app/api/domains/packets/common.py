"""
Common Packets Module - Packet Handler Registration Utilities

This module provides utility functions for registering packet handlers in the
osu! server application. It implements the decorator pattern for packet handler
registration, allowing packet handlers to be easily registered with the global
packet handler registry.

The module serves as a bridge between packet handler implementations and the
global packet registry system, providing a clean and consistent way to register
packet handlers for both regular and restricted packet types.

Key Features:
    - Decorator-based packet handler registration
    - Support for restricted packet handlers
    - Integration with global packet registry
    - Clean separation of concerns
    - Type-safe packet handler registration

Integration Points:
    - Packet handling in app/packets.py
    - Global state management in app/state/
    - Packet handler implementations in app/api/domains/cho.py
    - Restricted packet handling for anti-cheat

Usage Pattern:
    # Register a regular packet handler
    @register(ClientPackets.SEND_PUBLIC_MESSAGE)
    class SendMessage(BasePacket):
        async def handle(self, player: Player) -> None:
            # Handle public message
            pass
    
    # Register a restricted packet handler
    @register(ClientPackets.CHEAT_PACKET, restricted=True)
    class CheatPacket(BasePacket):
        async def handle(self, player: Player) -> None:
            # Handle cheat detection packet
            pass

Related Files:
    - app/packets.py: Packet definitions and base classes
    - app/state/__init__.py: Global state management
    - app/api/domains/cho.py: Packet handler implementations
"""

from pathlib import Path
import app.packets
import app.settings
import app.state
import app.usecases.performance
import app.utils
from collections.abc import Callable
import re

from app.packets import ClientPackets
from app.packets import BasePacket

def register(
    packet: ClientPackets,
    restricted: bool = False,
) -> Callable[[type[BasePacket]], type[BasePacket]]:
    """Register a handler in `app.state.packets`.
    
    This decorator function registers a packet handler class with the global
    packet registry. It supports both regular and restricted packet handlers,
    allowing for flexible packet handling based on player privileges.
    
    Args:
        packet: The ClientPackets enum value representing the packet type
        restricted: Whether this packet handler should be restricted to
                   privileged players only
    
    Returns:
        A decorator function that registers the packet handler class
    
    Example:
        @register(ClientPackets.SEND_PUBLIC_MESSAGE)
        class SendMessage(BasePacket):
            async def handle(self, player: Player) -> None:
                # Handle public message
                pass
    """

    def wrapper(cls: type[BasePacket]) -> type[BasePacket]:
        app.state.packets["all"][packet] = cls

        if restricted:
            app.state.packets["restricted"][packet] = cls

        return cls

    return wrapper