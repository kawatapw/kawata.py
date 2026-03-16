"""
Constants Package - Application-Wide Configuration and Enumerations

This module serves as the central hub for all application constants, enumerations,
and configuration values used throughout the osu! server application. It imports
and exposes all constant modules, providing a unified interface for accessing
game modes, mods, privileges, client flags, and regular expressions.

The package organizes constants into logical modules, each handling specific
aspects of the osu! server functionality. This includes game mechanics,
user privileges, client behavior flags, and pattern matching utilities.

Key Features:
    - Centralized access to all application constants
    - Modular organization of constant definitions
    - Type-safe enumerations for game mechanics
    - Regular expression patterns for validation
    - Privilege and permission definitions
    - Client flag interpretations

Integration Points:
    - Game mode handling in app/constants/gamemodes.py
    - Mod management in app/constants/mods.py
    - User privileges in app/constants/privileges.py
    - Client flags in app/constants/clientflags.py
    - Pattern matching in app/constants/regexes.py

Module Organization:
    - clientflags: Client behavior flag interpretations
    - gamemodes: Game mode enumerations and utilities
    - mods: Game modification flags and combinations
    - privileges: User privilege levels and permissions
    - regexes: Regular expression patterns for validation

Usage Pattern:
    # Import specific constants
    from app.constants import GameMode, Mods, Privileges
    
    # Import entire modules
    from app.constants import gamemodes
    from app.constants import mods
    
    # Access through package
    import app.constants
    mode = app.constants.GameMode.VANILLA_OSU

Related Files:
    - app/objects/: Data models using these constants
    - app/repositories/: Database operations with constants
    - app/usecases/: Business logic using constants
    - app/api/: API endpoints using constants
"""

# isort: dont-add-imports

from . import clientflags
from . import gamemodes
from . import mods
from . import privileges
from . import regexes
