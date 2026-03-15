"""
Settings Module - Application Configuration and Environment Management

This module provides centralized configuration management for the osu! server
application, loading and validating all environment variables and settings
required for server operation. It serves as the single source of truth for
all application configuration, ensuring consistent access to settings across
the entire codebase.

The module loads configuration from environment variables (typically from a
.env file) and provides typed access to all settings with appropriate defaults
and validation. It handles database connections, Redis configuration, API keys,
debug settings, and various server operational parameters.

Key Features:
    - Centralized configuration management from environment variables
    - Type-safe configuration access with automatic conversion
    - Database and Redis connection string generation
    - Debug and development mode configuration
    - Security settings and restrictions
    - External service integration (Discord, Datadog)
    - Performance tuning parameters
    - Version information from pyproject.toml

Integration Points:
    - Database connections in app/adapters/database.py
    - Redis connections in app/state/services.py
    - API authentication in app/api/
    - Debug logging in app/logging.py
    - External services in app/discord.py

Configuration Categories:
    - Application: Host, port, service name, container name
    - Database: MySQL connection parameters and DSN
    - Redis: Redis connection parameters and DSN
    - API: osu! API key, bot API key, domain settings
    - Debug: Debug level, focus, logging colors
    - Security: Disallowed names, passwords, client restrictions
    - External: Discord webhooks, Datadog monitoring
    - Performance: Cached accuracies, mirror endpoints

Usage Pattern:
    # Access configuration values
    from app import settings
    
    # Database connection
    db_dsn = settings.DB_DSN
    
    # Debug settings
    debug_level = settings.DEBUG_LEVEL
    
    # API keys
    api_key = settings.OSU_API_KEY
    
    # Feature flags
    if settings.DEVELOPER_MODE:
        enable_developer_features()

Related Files:
    - app/settings_utils.py: Configuration parsing utilities
    - app/adapters/database.py: Database connection using DB_DSN
    - app/state/services.py: Service initialization using settings
    - app/logging.py: Logging configuration using debug settings
"""

from __future__ import annotations

import os
import tomllib
from urllib.parse import quote

from dotenv import load_dotenv

from app.settings_utils import read_bool
from app.settings_utils import read_list

load_dotenv()

APP_HOST = os.environ["APP_HOST"]
APP_PORT = int(os.environ["APP_PORT"])

SERVICE_NAME = os.getenv("SERVICE_NAME", "osu_server")
CONTAINER_NAME = os.environ["CONTAINER_NAME"] or "bancho"


CHEAT_SERVER = os.environ["CHEAT_SERVER"]
CLIENT_VERSION = os.environ.get("CLIENT_VERSION") or None

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASS = quote(os.environ["DB_PASS"])
DB_NAME = os.environ["DB_NAME"]
DB_DSN = f"mysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
REDIS_USER = os.environ["REDIS_USER"]
REDIS_PASS = quote(os.environ["REDIS_PASS"])
REDIS_DB = int(os.environ["REDIS_DB"])

REDIS_AUTH_STRING = f"{REDIS_USER}:{REDIS_PASS}@" if REDIS_USER and REDIS_PASS else ""
REDIS_DSN = f"redis://{REDIS_AUTH_STRING}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

OSU_API_KEY = os.environ.get("OSU_API_KEY") or None
BOT_API_KEY = os.environ.get("BOT_API_KEY") or None # used for authorization in requests to b.py for admin related tasks. Please use only for frontend admin panel.

DOMAIN = os.environ["DOMAIN"]
USINGROOTDOMAIN = read_bool(os.environ["USINGROOTDOMAIN"]) # if true, server will accept osu.domain requests from the root domain as well as osu.domain
MIRROR_SEARCH_ENDPOINT = os.environ["MIRROR_SEARCH_ENDPOINT"]
MIRROR_DOWNLOAD_ENDPOINT = os.environ["MIRROR_DOWNLOAD_ENDPOINT"]

COMMAND_PREFIX = os.environ["COMMAND_PREFIX"]
REQUEST_PENDING_ONLY = read_bool(os.environ["REQUEST_PENDING_ONLY"])

SEASONAL_BGS = read_list(os.environ["SEASONAL_BGS"])

MENU_ICON_URL = os.environ["MENU_ICON_URL"]
MENU_ONCLICK_URL = os.environ["MENU_ONCLICK_URL"]

DATADOG_API_KEY = os.environ["DATADOG_API_KEY"]
DATADOG_APP_KEY = os.environ["DATADOG_APP_KEY"]

DEBUG_LEVEL = int(os.environ["DEBUG_LEVEL"])
DEBUG_FOCUS = os.environ["DEBUG_FOCUS"] or "all"
REDIRECT_OSU_URLS = read_bool(os.environ["REDIRECT_OSU_URLS"])

PP_CACHED_ACCURACIES = [int(acc) for acc in read_list(os.environ["PP_CACHED_ACCS"])]

DISALLOWED_NAMES = read_list(os.environ["DISALLOWED_NAMES"])
DISALLOWED_PASSWORDS = read_list(os.environ["DISALLOWED_PASSWORDS"])
DISALLOW_OLD_CLIENTS = read_bool(os.environ["DISALLOW_OLD_CLIENTS"])
DISALLOW_INGAME_REGISTRATION = read_bool(os.environ["DISALLOW_INGAME_REGISTRATION"])

DISCORD_AUDIT_LOG_WEBHOOK = os.environ["DISCORD_AUDIT_LOG_WEBHOOK"]
DISCORD_INVITE = os.environ["DISCORD_INVITE"]

AUTOMATICALLY_REPORT_PROBLEMS = read_bool(os.environ["AUTOMATICALLY_REPORT_PROBLEMS"])

LOG_WITH_COLORS = read_bool(os.environ["LOG_WITH_COLORS"])

# advanced dev settings

## WARNING touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE = read_bool(os.environ["DEVELOPER_MODE"])


with open("pyproject.toml", "rb") as f:
    VERSION = tomllib.load(f)["project"]["version"]
