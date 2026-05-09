"""
Application Package - Main Application Module

This module serves as the main entry point for the osu! server application,
initializing and importing all core modules required for server operation.
It acts as the central hub that connects all application components and
ensures proper module loading order during application startup.

The module imports and exposes all major application subsystems including
API endpoints, background tasks, command processing, constants, Discord
integration, logging, object models, packet handling, settings management,
state management, and utility functions.

Key Features:
    - Centralized module initialization and import management
    - Proper loading order for dependent modules
    - Clean namespace organization for all subsystems
    - Type ignore directives for import compatibility
    - Integration of all major application components

Integration Points:
    - API endpoints in app/api/
    - Background tasks in app/bg_loops.py
    - Command processing in app/commands.py
    - Constants and configuration in app/constants/
    - Discord integration in app/discord.py
    - Logging system in app/logging.py
    - Object models in app/objects/
    - Packet handling in app/packets.py
    - Settings management in app/settings.py
    - State management in app/state/
    - Utility functions in app/utils.py

Module Organization:
    - api: FastAPI application and route definitions
    - bg_loops: Background task management
    - commands: In-game command processing
    - constants: Application constants and enums
    - discord: Discord webhook integration
    - logging: Logging and error handling
    - objects: Data models and business objects
    - packets: Network packet handling
    - settings: Configuration management
    - state: Application state and sessions
    - utils: Utility functions and helpers

Usage Pattern:
    # Import the main application module
    from app import api, settings, state

    # Access application components
    app_instance = api.app
    config = settings
    sessions = state.sessions

    # Use imported modules
    from app.objects import Player
    from app.commands import command
    from app.logging import log

Related Files:
    - app/api/__init__.py: API application initialization
    - app/settings.py: Configuration settings
    - app/state/__init__.py: State management
    - app/logging.py: Logging utilities
    - app/utils.py: Utility functions
"""

# isort: dont-add-imports
from __future__ import annotations

from . import api
from . import bg_loops
from . import commands
from . import constants
from . import discord
from . import logging
from . import objects
from . import packets
from . import settings
from . import state
from . import utils

__all__ = [
    "api",
    "bg_loops",
    "commands",
    "constants",
    "discord",
    "logging",
    "objects",
    "packets",
    "settings",
    "state",
    "utils",
]
