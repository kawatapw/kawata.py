# CLAUDE.md — kawata.py Backend Service

This file provides guidance to Claude Code when working with the kawata.py backend. For cross-service architecture (Docker, nginx, shared DB, deployment), see `../CLAUDE.md`.

## Project Overview

**kawata.py** is a Python 3.11+ osu! private server based on bancho.py v5.2.2 (current version 5.3.0). It handles the Bancho binary protocol, score submission, beatmap mirroring, and a developer REST API. Built with FastAPI/Uvicorn.

**Upstream lineage:** bancho.py (cmyui/Akatsuki) → kawata.py (Kawata Team + Hina customizations)

## Code Ownership

| Owner | Scope | Rule |
|-------|-------|------|
| **Loki (base/upstream)** | Everything outside `hinaDir/` directories | Minimize changes; keep close to upstream |
| **Hina (custom)** | All `hinaDir/` directories | Free to modify |

### Detailed Ownership

| Path | Owner | Notes |
|------|-------|-------|
| `app/api/v1/api.py` | Loki | Base v1 API — avoid large modifications |
| `app/api/v1/hinaDir/` | Hina | Friends, PP records, future custom endpoints |
| `app/api/v2/` | Loki | RESTful CRUD API |
| `app/api/domains/cho.py` | Loki | Bancho protocol — very sensitive, avoid changes |
| `app/api/domains/osu.py` | Loki | Score submission — very sensitive |
| `app/api/domains/map.py` | Loki | Beatmap redirect |
| `app/constants/` | Loki | Shared constants (privileges, mods, gamemodes) |
| `app/objects/` | Loki | Domain objects (player, beatmap, score, match) |
| `app/repositories/` | Loki | Base data access layer |
| `app/repositories/hinaDir/` | Hina | Admin V2 logs, work items, review comments |
| `app/state/` | Loki | Global state management |
| `app/usecases/performance.py` | Loki | PP calculation |
| `app/logging.py` | Shared | Heavily customized logging infrastructure |
| `app/commands.py` | Loki | In-game chat commands |
| `migrations/` | Shared | `hinaDir_admin_v2.sql` is Hina-owned |

## Build & Run

### Makefile Targets

```bash
make build          # Docker build (bancho:latest)
make run            # docker compose up bancho mysql redis (foreground)
make run-bg         # Same but detached
make logs last=100  # Tail logs
make test           # Run tests via docker-compose.test.yml
make lint           # pre-commit run --all-files
make type-check     # mypy .
make install        # Poetry install (no dev)
make install-dev    # Poetry install + pre-commit hooks
make bump version=patch  # Bump version via poetry
```

### Docker

- **Base image:** `python:3.11-slim`
- **Workdir:** `/srv/root`
- **Dependencies:** Poetry 2.2.1, nginx, mysql-client, redis-tools
- **Entrypoint:** `scripts/start_server.sh`

Startup sequence:
1. `scripts/install-nginx-config.sh` — configure nginx
2. `scripts/wait-for-it.sh` — wait for MySQL and Redis
3. `python main.py` — start uvicorn

### Entry Point (`main.py`)

```python
uvicorn.run(
    "app.api.init_api:asgi_app",
    reload=(DEBUG_LEVEL >= 1),
    host=APP_HOST, port=APP_PORT,
    headers=[("bancho-version", VERSION)],
)
```

## Project Structure

```
kawata.py/
  main.py                           # Entry point (uvicorn runner)
  app/
    api/
      init_api.py                   # FastAPI app creation, lifespan, host-based routing
      __init__.py                   # Combines v1 + v2 routers into api_router
      middlewares.py                # MetricsMiddleware (request timing/logging)
      v1/
        __init__.py                 # Mounts v1 + hinaDir routers at /v1
        api.py                      # ~20 public + auth endpoints (1400+ lines)
        hinaDir/
          __init__.py               # Mounts friends + pp_records routers
          friends.py                # Friend/relationship system (7 endpoints)
          pp_records.py             # PP records with cheat value filtering
      v2/
        __init__.py                 # Mounts clans/maps/players/scores/client at /v2
        clans.py                    # GET /clans, GET /clans/{id}
        maps.py                     # GET /maps, GET /maps/{id}
        players.py                  # GET /players, GET /players/{id}, status, stats
        scores.py                   # GET /scores, GET /scores/{id}
        client.py                   # GET /changelog
        common/
          responses.py              # Success[T] / Failure response wrappers
          json.py                   # Custom JSON response handling
        models/                     # Pydantic v2 models for v2 endpoints
          clans.py, maps.py, players.py, scores.py
      domains/
        cho.py                      # Bancho binary protocol handler (~80+ packet handlers)
        osu.py                      # Score submission, screenshots, registration
        map.py                      # Beatmap redirect (→ b.ppy.sh)
        packets/
          common.py                 # Shared packet definitions
          aeris.py                  # Aeris client packet extensions
    constants/
      privileges.py                 # Privileges IntFlag, ClientPrivileges, ClanPrivileges, GetPriv()
      gamemodes.py                  # GameMode IntEnum (0-11, valid modes method)
      mods.py                       # Mods IntFlag (30+ mods), filter_invalid_combos(), dictionaries
      regexes.py                    # Pattern matching for names, URLs, etc.
      clientflags.py                # Anticheat flags (speed hacks, checksums)
      aeris_features.py             # Feature flags for Aeris client
    objects/
      player.py                     # Player class (~600+ lines): status, stats, friends, blocks
      beatmap.py                    # Beatmap with API fetching, caching, RankedStatus
      score.py                      # Score class with grade calc, SubmissionStatus
      match.py                      # Multiplayer match (16 slots, teams, win conditions)
      channel.py                    # Chat channel with permissions, auto-join
      collections.py                # In-memory collections: Players, Channels, Matches, Groups
      models.py                     # Shared model definitions
      achievement.py                # Achievement system
      badge.py                      # User badges
      badge_style.py                # Badge styling
      group.py                      # User groups
    repositories/
      users.py                      # User CRUD (priv, donor_end, clan_id, api_key)
      scores.py                     # Score management (ScoresTable + ScoreInfoTable)
      stats.py                      # Per-mode statistics
      maps.py                       # Beatmap repository with ranking status
      clans.py                      # Clan data access
      channels.py                   # Channel repository
      badges.py                     # Badge system (badges + badge_styles tables)
      logs.py                       # Legacy log table
      achievements.py               # Achievement repository
      user_achievements.py          # User-achievement junction
      comments.py                   # Beatmap comments
      ratings.py                    # Beatmap ratings
      favourites.py                 # User favourites
      client_hashes.py              # Hardware ID tracking
      ingame_logins.py              # Login history
      mail.py                       # In-game mail
      map_requests.py               # Beatmap rank requests
      tourney_pools.py              # Tournament map pools
      tourney_pool_maps.py          # Pool-map junction
      __init__.py                   # Base declarative metaclass
      hinaDir/
        admin_logs.py               # Admin V2 logging (action_type: 0=user, 1=map, 2=badge)
        work_items.py               # Beatmap review work items
        review_comments.py          # Comments on beatmap reviews
    state/
      services.py                   # Global services: Database, Redis, HTTP client, IP resolver, Datadog
      sessions.py                   # In-memory collections (players, channels, groups, matches, api_keys)
      cache.py                      # Caching: bcrypt, beatmap, beatmapset, unsubmitted, needs_update
      __init__.py                   # Module-level loop reference
    usecases/
      performance.py                # PP calc: ScoreParams, PerformanceResult, calculate_performances()
      achievements.py               # Achievement logic
      user_achievements.py          # User-specific achievement tracking
    adapters/
      database.py                   # Database wrapper (databases + SQLAlchemy query compilation)
    logging.py                      # Structured logging, Elasticsearch, error_catcher decorator
    commands.py                     # In-game chat commands (regular + mp/pool/clan command sets)
    bg_loops.py                     # Background tasks (donor expiry, ghost disconnect, bot status)
    discord.py                      # Discord webhook integration (Embed, Webhook classes)
    packets.py                      # Packet definitions (ClientPackets enum, server packet builders)
    encryption.py                   # Encryption utilities (rijndael)
    utils.py                        # Helpers: make_safe_name, achievement downloads, privilege checks
    timer.py                        # Performance timing context manager
    settings.py                     # All env config loaded from .env
    settings_utils.py               # read_bool(), read_list() helpers
    _typing.py                      # Custom types: IPAddress, UNSET sentinel
  migrations/
    base.sql                        # Base schema (~35KB)
    migrations.sql                  # Incremental version-based migrations (~43KB)
    hinaDir_admin_v2.sql            # Admin V2 tables (standalone)
  scripts/
    start_server.sh                 # Docker entrypoint
    install-nginx-config.sh         # Generates nginx web.conf from DOMAIN
    wait-for-it.sh                  # TCP connection waiter
    run-tests.sh                    # Test runner for Docker
    fix-multipart.sh                # Multipart fix script
  tools/
    recalc.py                       # PP recalculation tool
    proxy.py                        # mitmproxy helper
    migrate_logs.py                 # Log migration tool
  tests/
    conftest.py                     # Pytest fixtures, async support
    unit/packets_test.py            # Packet unit tests
    integration/domains/osu_test.py # Score submission integration tests
  testing/
    sample_data/                    # Sample data for tests
  pyproject.toml                    # Poetry config, mypy, pytest, isort settings
  Makefile                          # Build/run/test targets
  Dockerfile                        # Container definition
  .env.example                      # All configuration variables documented
  logging.yaml.example              # Logging config template
  .pre-commit-config.yaml           # Linting hooks
```

## Configuration (`app/settings.py`)

All settings loaded from `.env` via `python-dotenv`. Key variables:

| Variable | Purpose | Default/Example |
|----------|---------|-----------------|
| `APP_HOST` | Bind address | `0.0.0.0` |
| `APP_PORT` | Bind port | `10000` |
| `SERVICE_NAME` | Logging identifier | `kawata` |
| `CONTAINER_NAME` | Docker container name | `bancho` |
| `DOMAIN` | Server domain | `example.com` |
| `USINGROOTDOMAIN` | Accept osu requests on root domain | `False` |
| `DB_HOST/PORT/USER/PASS/NAME` | MariaDB connection | `mysql:3306/cmyui/lol123/banchopy` |
| `REDIS_HOST/PORT/USER/PASS/DB` | Redis connection | `redis:6379/default//0` |
| `OSU_API_KEY` | Official osu! API key (beatmaps) | — |
| `BOT_API_KEY` | Internal auth key for kawaweb→bancho | — |
| `CHEAT_SERVER` | Enable cheat server features | `False` |
| `DEBUG_LEVEL` | 0=INFO, 1=DBGLV1, 2=DBGLV2, 3=VERBOSE | `0` |
| `DEBUG_FOCUS` | Filter debug logs (`all`, `db`, etc.) | `all` |
| `PP_CACHED_ACCS` | Accuracy values for PP caching | `90,95,98,99,100` |
| `MIRROR_SEARCH_ENDPOINT` | Beatmap mirror search URL | `https://catboy.best/api/search` |
| `MIRROR_DOWNLOAD_ENDPOINT` | Beatmap mirror download URL | `https://catboy.best/d` |
| `COMMAND_PREFIX` | In-game command prefix | `!` |
| `DISALLOWED_NAMES` | Blocked usernames (comma-separated) | — |
| `DISALLOWED_PASSWORDS` | Blocked passwords (comma-separated) | — |
| `DISALLOW_OLD_CLIENTS` | Reject old osu! client versions | `True` |
| `DISALLOW_INGAME_REGISTRATION` | Block in-game account creation | `True` |
| `DISCORD_AUDIT_LOG_WEBHOOK` | Discord webhook for audit logs | — |
| `LOG_WITH_COLORS` | ANSI colors in console output | `False` |
| `DEVELOPER_MODE` | Dangerous dev features | `False` |

**VERSION** is read from `pyproject.toml` at import time.

**DB_DSN** is constructed as `mysql://{user}:{url_quoted_pass}@{host}:{port}/{name}`.

## Architecture

### Host-Based Request Routing (`app/api/init_api.py`)

The server uses FastAPI's `app.host()` for subdomain-based dispatch:

```python
for domain in ("ppy.sh", DOMAIN):
    for subdomain in ("c", "ce", "c4", "c5", "c6"):
        app.host(f"{subdomain}.{domain}", domains.cho.router)    # Bancho protocol
    app.host(f"osu.{domain}", domains.osu.router)                # Score submission
    if USINGROOTDOMAIN:
        app.host(f"{domain}", domains.osu.router)                # Root domain → osu
    app.host(f"b.{domain}", domains.map.router)                  # Beatmap redirect
    app.host(f"api.{domain}", api_router)                        # REST API (v1 + v2)
```

**Critical:** Requests to the API must have `Host: api.{domain}` header. Direct calls without the correct Host header result in 405 errors.

### Application Lifespan (`init_api.py:lifespan`)

Startup:
1. Ensure persistent volume directories exist
2. Connect to MySQL (`app.state.services.database.connect()`)
3. Connect to Redis (`app.state.services.redis.initialize()`)
4. Initialize Datadog (if configured)
5. Initialize IP resolver
6. Run SQL migrations (`app.state.services.run_sql_migrations()`)
7. Initialize RAM caches (`collections.initialize_ram_caches()`) — loads channels, groups, achievements, clans, BanchoBot
8. Start housekeeping background tasks

Shutdown:
1. Cancel housekeeping tasks
2. Close HTTP client, DB, Redis connections
3. Stop Datadog

### Middleware Stack

1. **MetricsMiddleware** (`app/api/middlewares.py`) — Logs every request with method, URL, status, timing, headers, client IP/country
2. **HTTP middleware** (inline in `init_api.py`) — Catches `ClientDisconnect` and `RuntimeError("No response returned")` from mid-request client disconnections

### State Management

**Global services** (`app/state/services`):
- `database` — `Database` wrapper around `databases` library with SQLAlchemy query compilation
- `redis` — `aioredis.Redis` client
- `http_client` — `httpx.AsyncClient` for external API calls
- `ip_resolver` — IP resolution from CF/nginx headers with caching
- `datadog` — Optional metrics client

**In-memory sessions** (`app/state/sessions`):
- `players: Players` — Online player collection (list-based with dict lookup)
- `channels: Channels` — Active chat channels
- `matches: Matches` — Active multiplayer matches (64-slot array)
- `groups: Groups` — User groups for permissions
- `api_keys: dict[str, int]` — Cached API key → user ID mapping
- `bot: Player` — BanchoBot player reference
- `housekeeping_tasks: set[asyncio.Task]` — Background task handles

**Caches** (`app/state/cache`):
- `bcrypt: dict[bytes, bytes]` — Password hash cache `{bcrypt_hash: md5_hash}`
- `beatmap: dict[str | int, Beatmap]` — Beatmap cache by md5 or ID
- `beatmapset: dict[int, BeatmapSet]` — Beatmap set cache
- `unsubmitted: set[str]` — Known unsubmitted map md5s
- `needs_update: set[str]` — Maps needing metadata refresh

### Background Tasks (`app/bg_loops.py`)

| Task | Interval | Purpose |
|------|----------|---------|
| `_remove_expired_donation_privileges` | 30 min | Revoke donor status from expired users |
| `_disconnect_ghosts` | ~100s | Disconnect idle clients past ping threshold |
| `_update_bot_status` | 5 min | Rotate BanchoBot's displayed status |
| `DebugLevelWatcher.watch` | 1s | Monitor debug level changes at runtime |

### Database Adapter (`app/adapters/database.py`)

Wraps the `databases` library with:
- SQLAlchemy `ClauseElement` compilation via `MySQLDialect` (named paramstyle)
- Error logging with query, params, and exception details on `MySQLError`
- Debug-level query timing logs (only when `DEBUG_LEVEL >= 2`)
- Methods: `fetch_one`, `fetch_all`, `fetch_val`, `execute`, `execute_many`, `transaction`

All methods return `None` on `MySQLError` (non-throwing) and log the error.

### Repository Pattern

Each repository module follows this structure:
1. **Table class** — SQLAlchemy declarative table definition
2. **READ_PARAMS** — Tuple of column names for SELECT queries
3. **TypedDict** — Return type definition
4. **CRUD functions** — Async functions using `app.state.services.database`

Example pattern:
```python
# app/repositories/users.py
class UsersTable(Base): ...
READ_PARAMS = ("id", "name", "safe_name", "priv", ...)
class User(TypedDict): ...

async def create(...) -> User: ...
async def fetch_one(...) -> User | None: ...
async def fetch_count(...) -> int: ...
async def fetch_many(...) -> list[User]: ...
async def partial_update(...) -> User | None: ...
```

Repositories:
- **Base:** users, scores, stats, maps, clans, channels, badges, logs, achievements, user_achievements, comments, ratings, favourites, client_hashes, ingame_logins, mail, map_requests, tourney_pools, tourney_pool_maps
- **hinaDir:** admin_logs, work_items, review_comments

## API Reference

### v1 Endpoints (`/v1/...`)

All mounted at `api.{domain}/v1/`. Responses use `ORJSONResponse`.

**Public (no auth):**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/calculate_pp` | Calculate PP for a beatmap with given params |
| GET | `/calculate_pp_batch` | Batch PP calculation |
| GET | `/search_players` | Search players by name |
| GET | `/get_player_count` | Online + total player counts |
| GET | `/get_player_info` | Detailed player profile |
| GET | `/get_player_status` | Current online status |
| GET | `/get_player_scores` | Player's scores (recent/best) |
| GET | `/get_player_most_played` | Most played beatmaps |
| GET | `/get_map_info` | Beatmap metadata |
| GET | `/get_map_scores` | Leaderboard for a map |
| GET | `/get_score_info` | Single score details |
| GET | `/get_replay` | Download replay file |
| GET | `/get_match` | Multiplayer match state |
| GET | `/get_leaderboard` | Global/country leaderboard |
| GET | `/get_top_players` | Top players by PP |
| GET | `/get_clan` | Clan details |
| GET | `/get_mappool` | Tournament map pool |
| GET | `/get_friends` | User's friend list (IDs) |
| GET | `/get_badges` | Badge listing |

**Authenticated (requires `Authorization: Bearer {api_key}`):**

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/update_map_status` | Change beatmap ranked status |

### v1 hinaDir Endpoints (`/v1/...`)

**Friends system:**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/get_friends_detailed` | None | Friends/followers/blocked with online status. `scope`: mutuals, followers, blocked, all |
| GET | `/get_friends_status` | None | Lightweight poll: online status for friends |
| POST | `/set_relationship` | BOT_API_KEY | Add/remove friend, block/unblock. Actions: add_friend, remove_friend, block, unblock |
| GET | `/get_friends_leaderboard` | None | Mutual friends + self ranked by PP |
| GET | `/get_player_quick_stats` | None | Stats + top play for one player |
| GET | `/compare_stats` | None | Side-by-side stats for 2-4 players |

**PP Records:**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/get_pp_records` | None | PP records with optional cheat_type/min/max filtering |

### v2 Endpoints (`/v2/...`)

RESTful CRUD with pagination. Responses use `Success[T]` / `Failure` wrappers.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/players` | List players (paginated) |
| GET | `/players/{id}` | Single player |
| GET | `/players/{id}/status` | Player online status |
| GET | `/players/{id}/stats/{mode}` | Player stats for mode |
| GET | `/players/{id}/stats` | Player stats (all modes) |
| GET | `/scores` | List scores (filtered) |
| GET | `/scores/{id}` | Single score |
| GET | `/maps` | List beatmaps (paginated) |
| GET | `/maps/{id}` | Single beatmap |
| GET | `/clans` | List clans |
| GET | `/clans/{id}` | Single clan |
| GET | `/changelog` | Server changelog |

### Domain Handlers

**`cho.py`** — Bancho binary protocol. Handles ~80+ packet types (login, status updates, chat, multiplayer, spectator, friend list, channel operations). Request/response is binary-packed data via `BanchoPacketReader` / server packet builders in `app/packets.py`.

**`osu.py`** — Score submission (`/web/osu-submit-modular-selector.php`), screenshots, registration (`/users`), seasonal backgrounds, client error reporting, direct search, leaderboards. Handles the osu! client's HTTP endpoints.

**`map.py`** — Redirects beatmap requests to `b.ppy.sh`.

## Constants

### Privileges (`app/constants/privileges.py`)

`Privileges(IntFlag)` — Server-side bitmask stored in `users.priv`:

| Value | Name | Value | Name |
|-------|------|-------|------|
| 0 | BANNED | 1 | UNRESTRICTED |
| 2 | VERIFIED | 4 | SUPPORTER |
| 8 | AccessPanel | 16 | ManageUsers |
| 32 | BanUsers | 64 | SilenceUsers |
| 128 | WipeUsers | 256 | ManageBeatmaps |
| 8192 | ManageBadges | 16384 | ViewPanelLog |
| 32768 | ManagePrivs | 65536 | SendAlerts |
| 131072 | ChatMod | 262144 | KickUsers |
| 1048576 | TOURNEY_MANAGER | 134217728 | ManageClans |
| 268435456 | ViewSensitiveInfo | 1073741824 | IsBot |
| 2147483648 | WHITELISTED | 4294967296 | PREMIUM |
| 8589934592 | ALUMNI | 17179869184 | DEVELOPER |

**Composite groups:**
- `NOMINATOR` = ManageBeatmaps | AccessPanel
- `SUPPORT` = BanUsers | SilenceUsers | WipeUsers | KickUsers | ChatMod | ViewPanelLog | SendAlerts | ManageClans | AccessPanel
- `MODERATOR` = SUPPORT | ManageUsers | ManageBadges | ViewSensitiveInfo
- `ADMINISTRATOR` = MODERATOR | ManagePrivs
- `DONATOR` = SUPPORTER | PREMIUM
- `STAFF` = NOMINATOR | SUPPORT | MODERATOR | ADMINISTRATOR | DEVELOPER

**Privilege checking pattern:**
```python
# Check if user has ALL privileges in a group:
if user_priv & Privileges.MODERATOR == Privileges.MODERATOR:

# Check if user has ANY privilege in a group:
if user_priv & Privileges.STAFF:
```

`GetPriv(int) -> list[Privileges]` decomposes an int to its constituent flags.
`GetPriv(list[Privileges]) -> int` combines flags to an int.

**ClientPrivileges** (sent to osu! client): PLAYER, MODERATOR, SUPPORTER, OWNER, DEVELOPER, TOURNAMENT

**ClanPrivileges** (IntEnum): Member=1, Officer=2, Owner=3

### Game Modes (`app/constants/gamemodes.py`)

```
0 = VANILLA_OSU       4 = RELAX_OSU       8 = AUTOPILOT_OSU
1 = VANILLA_TAIKO     5 = RELAX_TAIKO     9 = unused
2 = VANILLA_CATCH     6 = RELAX_CATCH    10 = unused
3 = VANILLA_MANIA     7 = unused         11 = unused
```

`GameMode.from_params(mode_vn, mods)` → adjusts mode based on RX/AP mod flags.
`GameMode.valid_gamemodes()` → excludes unused modes (7, 9, 10, 11).

### Mods (`app/constants/mods.py`)

`Mods(IntFlag)` with 30+ flags. Key utilities:
- `filter_invalid_combos(mode_vn)` — Removes conflicting mod combos (DTNC→NC, EZHR→EZ, etc.)
- `from_modstr("HDDTRX")` — Parse mod string
- `from_np(s, mode_vn)` — Parse /np format strings
- `get_mods_string(mods)` — Convert to readable string
- `SPEED_CHANGING_MODS` = DT | NC | HT
- `KEY_MODS` = KEY1-KEY9

## In-Game Commands (`app/commands.py`)

Commands are triggered by `COMMAND_PREFIX` (default `!`) in chat.

**Command system:**
- `Command` NamedTuple: triggers, callback, priv, hidden, doc
- `CommandSet`: grouped commands (mp, pool, clan)
- `Context` dataclass: player, trigger, args, recipient

**Regular commands** (by privilege level):
- **UNRESTRICTED:** help, roll, /np processing, last (recent score), mirror/bloodcat/q (map search), request, pingme
- **SUPPORTER:** changename
- **NOMINATOR:** requests (view pending), rank/unrank/love (map status)
- **MODERATOR:** ban, unban, silence, unsilence
- **ADMINISTRATOR:** user (lookup), alert, alertu, restrict, unrestrict, wipestats
- **DEVELOPER:** stealth, debug, reload, recalc, shutdown, restart

**Command sets:**
- `!mp` — Multiplayer management (start, abort, map, mods, team, invite, kick, etc.)
- `!pool` — Tournament mappool management (create, delete, add, remove, list, info)
- `!clan` — Clan management (create, delete, info, leave, list)

## PP Calculator (`app/usecases/performance.py`)

Uses **akatsuki-pp-py 1.0.0** (Rust-backed Python binding).

```python
@dataclass
class ScoreParams:
    mode: int
    mods: int | None = None
    combo: int | None = None
    acc: float | None = None        # OR n300/n100/n50/ngeki/nkatu/nmiss (not both)
    n300/n100/n50/ngeki/nkatu/nmiss: int | None = None

class PerformanceResult(TypedDict):
    performance: PerformanceRating   # pp, pp_acc, pp_aim, pp_speed, pp_flashlight, ...
    difficulty: DifficultyRating     # stars, aim, speed, flashlight, slider_factor, ...
```

`calculate_performances(osu_file_path, scores)` — Calculate PP for multiple scores on one beatmap.

**Important:** NC implies DT for the calculator — the code adds DT flag when NC is present.
NaN/Inf PP values are clamped to 0.0.

## Logging System (`app/logging.py`)

Custom structured logging with multiple outputs:

**Log levels** (`logLevel` IntEnum):
- 10=DEBUG, 11=VERBOSE, 14=DBGLV2, 16=DBGLV1, 20=INFO, 30=WARNING, 40=ERROR, 50=CRITICAL

**`log()` function** — Main logging entry point:
- Wraps stdlib logging with ANSI colors (controlled by `LOG_WITH_COLORS`)
- Routes to structlog loggers based on color/level
- Adds `@timestamp`, `Message`, calling function info
- At level >= 21: adds stack trace, function args, locals
- At level >= 40: adds full verbose stacktrace with exception details
- Supports `extra` dict with `filter.debugLevel` and `filter.debugFocus` for conditional logging

**`DebugFilter`** — Filters log records based on `DEBUG_LEVEL` and `DEBUG_FOCUS` settings.

**`error_catcher` decorator** — Wraps async/sync functions to catch all exceptions, log them with full traceback, and silently continue. Used on API endpoints to prevent crashes.

**CAUTION:** `error_catcher` swallows exceptions — endpoint returns `None` (no HTTP response) on error. This can cause confusing client-side behavior. Be aware when debugging.

**Additional outputs:** ElasticsearchHandler (optional), BytesJsonFormatter, StructlogFormatter.

## Migration System

**Version-based**, run automatically at startup by `app/state/services.run_sql_migrations()`.

Files:
- `migrations/base.sql` — Initial schema
- `migrations/migrations.sql` — Incremental updates with `# v{X.Y.Z}` version headers
- `migrations/hinaDir_admin_v2.sql` — Admin V2 tables (standalone)

**How migrations work:**
1. Read current version from `startups` table (last entry)
2. Compare against `VERSION` from `pyproject.toml`
3. Parse `migrations.sql` for version headers (`# v{X.Y.Z}`)
4. Execute all queries between `last_version < update_ver <= current_version`
5. Insert new startup record

**CRITICAL rules:**
- Use `#` comments ONLY, NEVER `--` — the runner joins multi-line SQL into single lines, so `--` comments out everything after the join point
- Multi-line SQL is joined with spaces; semicolons terminate queries
- No transaction wrapping (MySQL DDL auto-commits)
- Failures halt startup with `KeyboardInterrupt`

## Authentication

### API Authentication

**HTTPBearer** (`Authorization: Bearer {key}`):
- API keys stored in `users.api_key` column
- Cached in `app.state.sessions.api_keys` dict
- v1 authenticated endpoints validate against this

**BOT_API_KEY** (internal):
- Used for kawaweb → kawata.py requests
- Set via env var, validated in `users.api_key` for user ID 1
- Required for `/set_relationship` and `/update_map_status`

### Bancho Protocol Authentication

Password flow: `bcrypt(md5(plaintext))` — both server and client must use this exact scheme.

Login packet contains: username, password_md5, client info, timezone, display city flag.

## Data Paths

All data stored under `.data/` (mapped to `/srv/root/.data` in Docker):

| Path | Contents |
|------|----------|
| `.data/osu/` | Beatmap `.osu` files |
| `.data/osr/` | Replay files |
| `.data/avatars/` | User avatar images |
| `.data/ss/` | Screenshots |
| `.data/assets/medals/client/` | Achievement images |
| `.data/logs/` | Log files |
| `.data/logs/strange_occurrences/` | Pickled error objects |

## Redis Keys

| Key Pattern | Purpose |
|-------------|---------|
| `bancho:leaderboard:{mode}` | Global PP leaderboard (sorted set) |
| `bancho:leaderboard:{mode}:{country}` | Country PP leaderboard |

Modes: 0-3 (vanilla), 4-6 (relax), 8 (autopilot). Both kawata.py and kawaweb must use identical key format.

## Dependencies (Key)

From `pyproject.toml`:
- **fastapi** 0.109.2 + **uvicorn** 0.27.1 — Web framework
- **pydantic** 2.6.1 — Data validation
- **databases** 0.8.0 + **sqlalchemy** <1.5 + **aiomysql** — Database access
- **redis** 5.0.1 (with hiredis) — Cache/sessions
- **akatsuki-pp-py** 1.0.0 — PP calculation (Rust binding)
- **httpx** 0.26.0 — Async HTTP client
- **bcrypt** 4.1.2 — Password hashing
- **orjson** 3.9.13 — Fast JSON serialization
- **py3rijndael** 0.3.3 — Score encryption
- **structlog** + **python-json-logger** — Structured logging
- **elasticsearch** 8.13.2 — Optional log shipping
- **datadog** 0.48.0 — Optional metrics
- **tenacity** 8.2.3 — Retry logic (Discord webhooks)

Dev: pre-commit, black, isort, autoflake, mypy, pytest, pytest-asyncio, respx, coverage

## Code Style

- **Type checking:** mypy strict mode with pydantic plugin
- **Formatting:** black (via pre-commit)
- **Import sorting:** isort (force single line, profile=black), auto-adds `from __future__ import annotations`
- **Linting:** autoflake (remove unused imports)
- **Testing:** pytest with asyncio_mode="auto"

All files should start with `from __future__ import annotations`.

## Testing

```bash
make test        # Run via Docker (docker-compose.test.yml)
make lint        # pre-commit (black, isort, autoflake)
make type-check  # mypy strict
```

Test structure:
- `tests/unit/packets_test.py` — Packet serialization tests
- `tests/integration/domains/osu_test.py` — Score submission tests
- `tests/conftest.py` — Shared fixtures
- `testing/sample_data/` — Test data

## Common Patterns

### Adding a New v1 Endpoint

1. Add route handler to `app/api/v1/api.py` (base) or `app/api/v1/hinaDir/{module}.py` (custom)
2. Use `@router.get("/endpoint_name")` or `@router.post(...)`
3. Apply `@error_catcher` decorator for exception handling
4. Access DB via `app.state.services.database.fetch_one/fetch_all/execute`
5. Access Redis via `app.state.services.redis`
6. Return `ORJSONResponse({"status": "success", ...})`

### Adding a New v2 Endpoint

1. Add route to `app/api/v2/{module}.py`
2. Create Pydantic model in `app/api/v2/models/{module}.py` if needed
3. Use `Success` / `Failure` response wrappers from `app/api/v2/common/responses.py`
4. Register router in `app/api/v2/__init__.py` if new module

### Adding a New Repository

1. Create `app/repositories/{name}.py`
2. Define `Table(Base)` class with SQLAlchemy columns
3. Define `READ_PARAMS` tuple
4. Define `TypedDict` return type
5. Implement async CRUD functions

### Adding a New hinaDir Endpoint

1. Create file in `app/api/v1/hinaDir/{name}.py`
2. Define `router = APIRouter()`
3. Import and include in `app/api/v1/hinaDir/__init__.py`

### Adding a Migration

1. Add to `migrations/migrations.sql` under a new `# v{X.Y.Z}` header
2. Bump version in `pyproject.toml` to match: `make bump version=patch`
3. Use `#` comments only — NEVER `--`
4. Each statement must end with `;`

## Gotchas

| Issue | Cause / Fix |
|-------|-------------|
| API returns 405 | Missing `Host: api.{domain}` header on request |
| API returns 401 | `users.api_key` not set for user ID 1. Check BOT_API_KEY in DB |
| `error_catcher` silences errors | Decorator catches ALL exceptions and returns None. Check logs for error details |
| PP calc returns 0 | NaN/Inf result clamped to 0. Check beatmap file exists in `.data/osu/` |
| `--` in migration SQL | NEVER use `--` comments. Runner joins lines, making `--` comment out subsequent SQL |
| Password mismatch | Must use `bcrypt(md5(plaintext))` — not `bcrypt(plaintext)` |
| Beatmap cache stale | In-memory cache not invalidated. Must call API to change map status (not direct DB write) |
| `fetch_all` / `execute` returns None | `MySQLError` was caught and logged. Check logs for SQL error details |
| Redis leaderboard wrong | Key format must be `bancho:leaderboard:{mode}` — mode 0-3 vanilla, 4-6 relax, 8 autopilot |
| Debug logs not showing | Check `DEBUG_LEVEL` and `DEBUG_FOCUS` settings match the log's filter |
| uvicorn hot-reload | Only enabled when `DEBUG_LEVEL >= 1` |

## Discord Integration (`app/discord.py`)

Webhook client with embed support. Classes: `Webhook`, `Embed`, `Footer`, `Image`, `Thumbnail`, `Author`, `Field`.

Uses `tenacity` retry (10 attempts, exponential backoff 4-10s). Posts via `services.http_client`.

```python
webhook = Webhook(url, username="Bot")
embed = Embed(title="Event", color=0xFF0000)
embed.add_field("User", username)
webhook.add_embed(embed)
await webhook.post()
```

## IP Resolution (`app/state/services.py`)

Resolves client IP from headers with priority:
1. `CF-Connecting-IP` (Cloudflare)
2. `X-Forwarded-For` (first entry if multiple)
3. `X-Real-IP` (nginx)

Geolocation resolved from:
1. Cloudflare headers (`CF-IPCountry`, `CF-IPLatitude`, `CF-IPLongitude`)
2. Nginx geo headers (`X-Country-Code`, `X-Latitude`, `X-Longitude`)
3. Fallback: `ip-api.com` HTTP API

Results cached in `IPResolver.cache`.

## OpenAPI Documentation

`BanchoAPI` subclass overrides `openapi()` to include host-mounted routes in the schema (FastAPI normally excludes them). Docs available at `api.{domain}/docs`.
