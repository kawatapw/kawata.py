"""
Objects Package - Core Data Models and Business Logic

This module serves as the central package for all core data models and business
logic objects used throughout the osu! server application. It imports and
exposes all major object modules, providing a unified interface for accessing
player data, game objects, achievements, and other core functionality.

The package organizes the application's domain models into logical modules,
each handling specific aspects of the osu! server functionality. This includes
player management, game mechanics, achievement tracking, and various game
objects like beatmaps, channels, and matches.

Key Features:
    - Centralized access to all core data models
    - Modular organization of business logic
    - Clean separation of concerns
    - Type-safe object interfaces
    - Integration with database repositories

Integration Points:
    - Achievement system in app/objects/achievement.py
    - Beatmap management in app/objects/beatmap.py
    - Channel management in app/objects/channel.py
    - Collection utilities in app/objects/collections.py
    - Match system in app/objects/match.py
    - Data models in app/objects/models.py
    - Player management in app/objects/player.py
    - Score tracking in app/objects/score.py

Module Organization:
    - achievement: Player achievement tracking and validation
    - beatmap: Beatmap data and metadata management
    - channel: Chat channel and communication handling
    - collections: Utility collections and data structures
    - match: Multiplayer match management
    - models: Pydantic data models for API responses
    - player: Player data, sessions, and authentication
    - score: Score submission and tracking

Usage Pattern:
    # Import specific objects
    from app.objects import Player, Beatmap, Score
    
    # Import entire modules
    from app.objects import achievement
    from app.objects import beatmap
    
    # Access through package
    import app.objects
    player = app.objects.Player(...)

Related Files:
    - app/repositories/: Database access layer
    - app/state/: Application state management
    - app/usecases/: Business logic layer
    - app/api/: API endpoints and handlers
"""

# type: ignore
# isort: dont-add-imports

from . import achievement
from . import beatmap
from . import channel
from . import collections
from . import match
from . import models
from . import player
from . import score
