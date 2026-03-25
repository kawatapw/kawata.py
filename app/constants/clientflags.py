"""
ClientFlags Module - Anti-Cheat Flag Constants for osu! Client Detection

This module defines bitwise flag constants used by the osu! anti-cheat system to detect
and flag suspicious client behavior. These flags are sent by the osu! client to the
server and indicate various types of potential cheating or anomalous behavior.

The module contains two main flag classes:
1. ClientFlags: Legacy anti-cheat flags from osu! client versions up to 2016
2. LastFMFlags: Updated anti-cheat flags from osu! client version 2019

These flags are used throughout the codebase to:
- Detect and flag suspicious player behavior
- Validate score submissions for potential cheating
- Monitor client-side anomalies and timing discrepancies
- Identify known cheat software signatures

Integration Points:
    - Score submission validation in app/api/domains/osu.py
    - Player session monitoring in app/objects/player.py
    - Anti-cheat analysis in app/usecases/achievements.py
    - Database logging in app/repositories/scores.py

Usage Pattern:
    - Flags are received from the osu! client during gameplay
    - They are stored as bitwise integers in player session data
    - Multiple flags can be combined using bitwise OR operations
    - Flag checking uses bitwise AND operations: (flags & ClientFlags.SPEED_HACK_DETECTED)

Security Considerations:
    - Many legacy flags are outdated and prone to false positives
    - Flags should be used as indicators, not definitive proof of cheating
    - The CLEAN flag (0) indicates no suspicious behavior detected
    - Flag combinations can indicate more sophisticated cheating methods

Historical Context:
    - ClientFlags: Original anti-cheat system from early osu! versions
    - LastFMFlags: Updated system from 2019 with improved detection methods
    - Some flags target specific known cheat software (e.g., AQN)
    - Flags are maintained for backward compatibility and historical analysis

Example Usage:
    # Check if speed hack was detected
    if player.client_flags & ClientFlags.SPEED_HACK_DETECTED:
        flag_player_for_review()

    # Check for multiple cheat indicators
    suspicious_flags = ClientFlags.SPEED_HACK_DETECTED | ClientFlags.RAW_MOUSE_DISCREPANCY
    if player.client_flags & suspicious_flags:
        investigate_player(player)

Related Files:
    - app/objects/player.py: Player class storing client flags
    - app/api/domains/osu.py: Score submission handling with flag validation
    - app/usecases/achievements.py: Achievement validation using flag data
    - app/repositories/scores.py: Database storage of flag information
"""

from __future__ import annotations

from enum import IntFlag, unique

from app.utils import escape_enum, pymysql_encode


@unique
@pymysql_encode(escape_enum)
class ClientFlags(IntFlag):
    """osu! anticheat <= 2016 (unsure of age)"""

    # NOTE: many of these flags are quite outdated and/or
    # broken and are even known to false positive quite often.
    # they can be helpful; just take them with a grain of salt.

    CLEAN = 0  # no flags sent

    # flags for timing errors or desync.
    SPEED_HACK_DETECTED = 1 << 1

    # this is to be ignored by server implementations. osu! team trolling hard
    INCORRECT_MOD_VALUE = 1 << 2

    MULTIPLE_OSU_CLIENTS = 1 << 3
    CHECKSUM_FAILURE = 1 << 4
    FLASHLIGHT_CHECKSUM_INCORRECT = 1 << 5

    # these are only used on the osu!bancho official server.
    OSU_EXECUTABLE_CHECKSUM = 1 << 6
    MISSING_PROCESSES_IN_LIST = 1 << 7  # also deprecated as of 2018

    # flags for either:
    # 1. pixels that should be outside the visible radius
    # (and thus black) being brighter than they should be.
    # 2. from an internal alpha value being incorrect.
    FLASHLIGHT_IMAGE_HACK = 1 << 8

    SPINNER_HACK = 1 << 9
    TRANSPARENT_WINDOW = 1 << 10

    # (mania) flags for consistently low press intervals.
    FAST_PRESS = 1 << 11

    # from my experience, pretty decent
    # for detecting autobotted scores.
    RAW_MOUSE_DISCREPANCY = 1 << 12
    RAW_KEYBOARD_DISCREPANCY = 1 << 13


@unique
@pymysql_encode(escape_enum)
class LastFMFlags(IntFlag):
    """osu! anticheat 2019"""

    # XXX: the aqn flags were fixed within hours of the osu!
    # update, and vanilla hq is not so widely used anymore.
    RUN_WITH_LD_FLAG = 1 << 14
    CONSOLE_OPEN = 1 << 15
    EXTRA_THREADS = 1 << 16
    HQ_ASSEMBLY = 1 << 17
    HQ_FILE = 1 << 18
    REGISTRY_EDITS = 1 << 19
    SDL2_LIBRARY = 1 << 20
    OPENSSL_LIBRARY = 1 << 21
    AQN_MENU_SAMPLE = 1 << 22
