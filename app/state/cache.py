"""
Cache Module - In-Memory Data Caching for Performance Optimization

This module provides global in-memory cache dictionaries for storing frequently
accessed data in the osu! server application. These caches significantly improve
performance by reducing database queries and API calls for commonly accessed
information like beatmaps, beatmap sets, and password hashes.

The cache system uses simple dictionary and set data structures for fast lookups
and is designed to be populated during server startup and updated during normal
operation. The caches are shared across all application components through the
global state management system.

Key Features:
    - In-memory caching for frequently accessed data
    - Fast dictionary and set-based lookups
    - Support for multiple key types (string, int, bytes)
    - Beatmap and beatmap set caching for score submission
    - Password hash caching for authentication performance
    - Unsubmitted and update-needed tracking for beatmap management
    - Type hints for better code documentation and IDE support

Integration Points:
    - Beatmap management in app/objects/beatmap.py
    - Score submission in app/api/domains/osu.py
    - Authentication in app/api/domains/cho.py
    - Beatmap updates in app/repositories/maps.py
    - Application state in app/state/__init__.py

Cache Structures:
    - bcrypt: Password hash cache mapping bcrypt hashes to MD5 hashes
    - beatmap: Beatmap cache mapping MD5 hashes and IDs to Beatmap objects
    - beatmapset: Beatmap set cache mapping set IDs to BeatmapSet objects
    - unsubmitted: Set of MD5 hashes for beatmaps not yet submitted
    - needs_update: Set of MD5 hashes for beatmaps requiring updates

Usage Pattern:
    # Access beatmap cache
    beatmap = app.state.cache.beatmap.get(md5_hash)
    beatmap = app.state.cache.beatmap.get(beatmap_id)

    # Access beatmap set cache
    beatmap_set = app.state.cache.beatmapset.get(set_id)

    # Check password hash cache
    md5_hash = app.state.cache.bcrypt.get(bcrypt_hash)

    # Check unsubmitted beatmaps
    if md5_hash in app.state.cache.unsubmitted:
        handle_unsubmitted_beatmap(md5_hash)

    # Check beatmaps needing updates
    if md5_hash in app.state.cache.needs_update:
        update_beatmap(md5_hash)

Related Files:
    - app/objects/beatmap.py: Beatmap and BeatmapSet classes
    - app/state/__init__.py: Application state management
    - app/state/services.py: Service initialization
    - app/repositories/maps.py: Database operations for beatmaps
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.objects.beatmap import Beatmap, BeatmapSet


bcrypt: dict[bytes, bytes] = {}  # {bcrypt: md5, ...}
beatmap: dict[str | int, Beatmap] = {}  # {md5: map, id: map, ...}
beatmapset: dict[int, BeatmapSet] = {}  # {bsid: map_set}
unsubmitted: set[str] = set()  # {md5, ...}
needs_update: set[str] = set()  # {md5, ...}
