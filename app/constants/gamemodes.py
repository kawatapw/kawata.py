"""
GameModes Module - osu! Game Mode Enumeration and Utilities

This module defines the GameMode enumeration and related utilities for handling
different osu! game modes, including vanilla, relax, and autopilot variants.
It provides a comprehensive mapping of all supported game modes and helper
methods for mode conversion and validation.

The module supports three main game mode categories:
1. Vanilla modes: Standard osu! gameplay (osu!, taiko, catch, mania)
2. Relax modes: Auto-pilot assistance for cursor movement (rx! prefix)
3. Autopilot modes: Auto-pilot assistance for clicking (ap! prefix)

Key Features:
    - Complete enumeration of all supported game modes
    - Conversion between vanilla and modded game modes
    - Validation of valid game modes (excluding unused combinations)
    - String representation for logging and display
    - Integration with the Mods system for mode detection

Integration Points:
    - Score submission handling in app/api/domains/osu.py
    - Player statistics tracking in app/repositories/stats.py
    - Leaderboard generation in app/api/v2/players.py
    - Achievement validation in app/usecases/achievements.py
    - Database storage in app/repositories/scores.py

Usage Pattern:
    - Game modes are typically determined from player mods and base mode
    - The from_params() class method converts vanilla mode + mods to GameMode
    - The as_vanilla property converts any mode back to its vanilla equivalent
    - String representation uses the GAMEMODE_REPR_LIST for display

Mode Mapping:
    - Vanilla modes (0-3): Standard gameplay without assistance
    - Relax modes (4-7): Cursor movement assistance (rx! prefix)
    - Autopilot modes (8-11): Clicking assistance (ap! prefix)
    - Unused modes: RELAX_MANIA, AUTOPILOT_TAIKO, AUTOPILOT_CATCH, AUTOPILOT_MANIA

Example Usage:
    # Convert vanilla mode with relax mod to GameMode
    mode = GameMode.from_params(0, Mods.RELAX)  # Returns RELAX_OSU

    # Get vanilla equivalent of any mode
    vanilla_mode = GameMode.RELAX_OSU.as_vanilla  # Returns 0

    # Get string representation
    mode_str = repr(GameMode.VANILLA_OSU)  # Returns "vn!std"

    # Get list of valid game modes
    valid_modes = GameMode.valid_gamemodes()

Related Files:
    - app/constants/mods.py: Mods enumeration for game modifications
    - app/objects/player.py: Player class using game modes
    - app/api/domains/osu.py: Score submission with mode validation
    - app/repositories/stats.py: Statistics tracking per game mode
"""

from __future__ import annotations

import functools
from enum import IntEnum
from enum import unique

from app.constants.mods import Mods
from app.utils import escape_enum
from app.utils import pymysql_encode

GAMEMODE_REPR_LIST = (
    "vn!std",
    "vn!taiko",
    "vn!catch",
    "vn!mania",
    "rx!std",
    "rx!taiko",
    "rx!catch",
    "rx!mania",  # unused
    "ap!std",
    "ap!taiko",  # unused
    "ap!catch",  # unused
    "ap!mania",  # unused
)


@unique
@pymysql_encode(escape_enum)
class GameMode(IntEnum):
    VANILLA_OSU = 0
    VANILLA_TAIKO = 1
    VANILLA_CATCH = 2
    VANILLA_MANIA = 3

    RELAX_OSU = 4
    RELAX_TAIKO = 5
    RELAX_CATCH = 6
    RELAX_MANIA = 7  # unused

    AUTOPILOT_OSU = 8
    AUTOPILOT_TAIKO = 9  # unused
    AUTOPILOT_CATCH = 10  # unused
    AUTOPILOT_MANIA = 11  # unused

    @classmethod
    def from_params(cls, mode_vn: int, mods: Mods) -> GameMode:
        mode = mode_vn

        if mods & Mods.AUTOPILOT:
            mode += 8
        elif mods & Mods.RELAX:
            mode += 4

        return cls(mode)

    @classmethod
    @functools.cache
    def valid_gamemodes(cls) -> list[GameMode]:
        ret = []
        for mode in cls:
            if mode not in (
                cls.RELAX_MANIA,
                cls.AUTOPILOT_TAIKO,
                cls.AUTOPILOT_CATCH,
                cls.AUTOPILOT_MANIA,
            ):
                ret.append(mode)
        return ret

    @property
    def as_vanilla(self) -> int:
        return self.value % 4

    def __repr__(self) -> str:
        return GAMEMODE_REPR_LIST[self.value]
