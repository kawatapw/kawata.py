from __future__ import annotations

import os
import tomllib

from dotenv import load_dotenv

from app.settings_utils import read_bool
from app.settings_utils import read_list

load_dotenv()

APP_HOST = os.environ["APP_HOST"]
APP_PORT = int(os.environ["APP_PORT"])
# Set some values at server start
OLD_CLIENT_SCORE_SUBMIT_LOG_COUNT = 0

APP_TZ = os.environ["APP_TZ"]
CHEAT_SERVER = read_bool(os.environ["CHEAT_SERVER"])

DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASS = os.environ["DB_PASS"]
DB_NAME = os.environ["DB_NAME"]
DB_DSN = f"mysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
REDIS_USER = os.environ["REDIS_USER"]
REDIS_PASS = os.environ["REDIS_PASS"]
REDIS_DB = int(os.environ["REDIS_DB"])

REDIS_AUTH_STRING = f"{REDIS_USER}:{REDIS_PASS}@" if REDIS_USER and REDIS_PASS else ""
REDIS_DSN = f"redis://{REDIS_AUTH_STRING}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

OSU_API_KEY = os.environ.get("OSU_API_KEY") or None
ORDR_API_KEY = os.environ["ORDR_API_KEY"]
BOT_API_KEY = os.environ["BOT_API_KEY"] # used for authorization in requests to b.py for admin related tasks. Please use only for frontend admin panel.

DOMAIN = os.environ["DOMAIN"]
MIRROR_SEARCH_ENDPOINT = os.environ["MIRROR_SEARCH_ENDPOINT"]
MIRROR_DOWNLOAD_ENDPOINT = os.environ["MIRROR_DOWNLOAD_ENDPOINT"]

COMMAND_PREFIX = os.environ["COMMAND_PREFIX"]
REQUEST_PENDING_ONLY = read_bool(os.environ["REQUEST_PENDING_ONLY"])
UNREAD_MESSAGES = read_bool(os.environ["UNREAD_MESSAGES"])

SEASONAL_BGS = read_list(os.environ["SEASONAL_BGS"])

MENU_ICON_URL = os.environ["MENU_ICON_URL"]
MENU_ONCLICK_URL = os.environ["MENU_ONCLICK_URL"]

DATADOG_API_KEY = os.environ["DATADOG_API_KEY"]
DATADOG_APP_KEY = os.environ["DATADOG_APP_KEY"]

DEBUG = read_bool(os.environ["DEBUG"])
DEBUG_LEVEL = os.environ["DEBUG_LEVEL"]
DEBUG_CLIENT = read_bool(os.environ["DEBUG_CLIENT"])
DEBUG_REQUESTS = read_bool(os.environ["DEBUG_REQUESTS"])
DEBUG_SCORES = read_bool(os.environ["DEBUG_SCORES"])
DEBUG_MESSAGES = read_bool(os.environ["DEBUG_MESSAGES"])
DEBUG_LEADERBOARDS = read_bool(os.environ["DEBUG_LEADERBOARDS"])
REDIRECT_OSU_URLS = read_bool(os.environ["REDIRECT_OSU_URLS"])

PP_CACHED_ACCURACIES = [int(acc) for acc in read_list(os.environ["PP_CACHED_ACCS"])]

DISALLOWED_NAMES = read_list(os.environ["DISALLOWED_NAMES"])
DISALLOWED_PASSWORDS = read_list(os.environ["DISALLOWED_PASSWORDS"])
DISALLOW_OLD_CLIENTS = read_bool(os.environ["DISALLOW_OLD_CLIENTS"])
DISALLOW_INGAME_REGISTRATION = read_bool(os.environ["DISALLOW_INGAME_REGISTRATION"])

DISCORD_AUDIT_LOG_WEBHOOK = os.environ["DISCORD_AUDIT_LOG_WEBHOOK"]

AUTOMATICALLY_REPORT_PROBLEMS = read_bool(os.environ["AUTOMATICALLY_REPORT_PROBLEMS"])
# Social Links used in game
DISCORD_LINK = os.environ["DISCORD_LINK"]

# advanced dev settings

## WARNING touch this once you've
##          read through what it enables.
##          you could put your server at risk.
DEVELOPER_MODE = read_bool(os.environ["DEVELOPER_MODE"])

with open("pyproject.toml", "rb") as f:
    VERSION = tomllib.load(f)["tool"]["poetry"]["version"]
