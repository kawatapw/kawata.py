"""
Regexes Module - Regular Expression Patterns for Input Validation

This module defines compiled regular expression patterns used throughout the
osu! server application for validating and parsing various types of user input
and data formats. These regex patterns ensure data integrity and security by
validating usernames, email addresses, osu! client versions, and tournament
match information.

The module provides pre-compiled regex patterns for optimal performance, as
compiling regex patterns at module load time is more efficient than compiling
them repeatedly during runtime. The patterns are used extensively in input
validation, data parsing, and security checks across the application.

Key Features:
    - Pre-compiled regex patterns for performance optimization
    - Support for both standard and cheat server configurations
    - Comprehensive validation for usernames, emails, and version strings
    - Tournament match name parsing with team extraction
    - Map pool pick format validation
    - Best-of series format validation

Integration Points:
    - User registration in app/api/domains/cho.py
    - Client version validation in app/api/domains/osu.py
    - Tournament management in app/api/v2/players.py
    - Email validation in app/repositories/users.py
    - Match parsing in app/objects/match.py

Pattern Descriptions:
    - OSU_VERSION: Validates osu! client version strings (e.g., "b20231215.1")
    - USERNAME: Validates usernames (2-15 characters, alphanumeric with spaces/brackets)
    - EMAIL: Validates email addresses with domain and TLD validation
    - TOURNEY_MATCHNAME: Parses tournament match names with team extraction
    - MAPPOOL_PICK: Validates map pool pick format (e.g., "NM1", "HD2")
    - BEST_OF: Validates best-of series format (e.g., "bo7", "7")

Usage Pattern:
    - Patterns are imported and used directly for validation
    - Match objects provide access to captured groups
    - Patterns are used with re.match() or re.search() functions
    - Named groups provide semantic access to captured data

Example Usage:
    # Validate username
    if USERNAME.match(username):
        create_user(username)
    
    # Parse osu! version
    match = OSU_VERSION.match(version_string)
    if match:
        date = match.group("date")
        stream = match.group("stream")
    
    # Parse tournament match name
    match = TOURNEY_MATCHNAME.match(match_name)
    if match:
        team1 = match.group("T1")
        team2 = match.group("T2")

Related Files:
    - app/settings.py: Settings module for CHEAT_SERVER configuration
    - app/api/domains/cho.py: Client connection with username validation
    - app/api/domains/osu.py: Score submission with version validation
    - app/objects/match.py: Match object with tournament name parsing
"""

from __future__ import annotations
import app.settings
import re

if app.settings.CHEAT_SERVER:
    OSU_VERSION = re.compile(
        r"^(?:Abypass Client )?b(?P<date>\d{8})(?:\.(?P<revision>\d+))?"
        r"(?P<stream>beta|cuttingedge|dev|tourney|Aeris)?$",
    )
else:
    OSU_VERSION = re.compile(
    r"^b(?P<date>\d{8})(?:\.(?P<revision>\d+))?"
    r"(?P<stream>beta|cuttingedge|dev|tourney)?$",
)

USERNAME = re.compile(r"^[\w \[\]-]{2,15}$")
EMAIL = re.compile(r"^[^@\s]{1,200}@[^@\s\.]{1,30}(?:\.[^@\.\s]{2,24})+$")

TOURNEY_MATCHNAME = re.compile(
    r"^(?P<name>[a-zA-Z0-9_ ]+): "
    r"\((?P<T1>[a-zA-Z0-9_ ]+)\)"
    r" vs\.? "
    r"\((?P<T2>[a-zA-Z0-9_ ]+)\)$",
    flags=re.IGNORECASE,
)

MAPPOOL_PICK = re.compile(r"^([a-zA-Z]+)([0-9]+)$")

BEST_OF = re.compile(r"^(?:bo)?(\d{1,2})$")
