# CLAUDE.md — kawata.py Backend Service

This file provides guidance to Claude Code when working with the kawata.py backend. For cross-service architecture (Docker, nginx, shared DB, deployment), see `../CLAUDE.md`.

> **Public repo:** this codebase is published as `alejandroatacho/hina-kawata.py` (fork of upstream `kawatapw/kawata.py`). Source files in this repo must NOT contain comments or docstrings. THIS CLAUDE.md is documentation — verbose is fine here.

## Project Overview

**kawata.py** is a Python 3.11 osu! private server derived from bancho.py (current: **v5.3.2**). It speaks the Bancho binary protocol, handles score submission, proxies beatmap mirroring, and exposes a developer REST API (v1 + v2). Built with FastAPI/Uvicorn on top of Starlette host-based routing.

**Upstream lineage:** bancho.py (cmyui/Akatsuki) → kawata.py (kawatapw) → Hina fork (`alejandroatacho/hina-kawata.py`).

**Tracked branches in the Hina fork:**
- `BE-Dev` — primary development target (current HEAD on this working copy).
- `BE-Staging` — pre-prod release candidate; receives merges from `BE-Dev`.
- `BE-Prod` — production; image published as `be-prod` / `latest` on Docker Hub.
- Upstream remote `upstream` tracks `kawatapw/kawata.py` (BE-Dev / BE-Staging / BE-Prod).

## Code Ownership

| Owner | Scope | Rule |
|-------|-------|------|
| **Loki (base/upstream)** | Everything outside `hinaDir/` | Keep close to upstream; minimize drift |
| **Hina (custom)** | All `hinaDir/` directories | Free to modify |

CODEOWNERS: the whole repo is default-owned by `@TheFantasticLoki` (upstream maintainer).

### Detailed Ownership

| Path | Owner | Notes |
|------|-------|-------|
| `app/api/v1/api.py` | Loki | ~1.9k lines, 21 endpoints — avoid structural changes |
| `app/api/v1/hinaDir/` | Hina | friends, pp_records — Hina's v1 extensions |
| `app/api/v2/` | Loki | RESTful CRUD (players, scores, maps, clans, client, seasons) |
| `app/api/domains/cho.py` | Loki | Bancho binary protocol — very sensitive |
| `app/api/domains/osu.py` | Loki | Score submission, registration — very sensitive |
| `app/api/domains/map.py` | Loki | Beatmap redirect |
| `app/api/domains/packets/` | Loki | Packet handler registration + Aeris extensions |
| `app/constants/` | Loki | privileges, mods, gamemodes, clientflags, regexes, aeris_features |
| `app/objects/` | Loki | Domain objects (Player, Beatmap, Score, Match, Channel, Collections, …) |
| `app/repositories/` | Loki | Base data access layer |
| `app/repositories/hinaDir/` | Hina | admin V2 logs, beatmap work items, review comments |
| `app/state/` | Loki | Global services + in-memory sessions + caches |
| `app/usecases/performance.py` | Loki | PP calculation (akatsuki-pp-py 1.0.0) |
| `app/schedule_types/` | Loki | Season schedule providers (manual / seasonal / IFC / fixed) |
| `app/logging.py` | Shared | Heavily customized logging infrastructure |
| `app/commands.py` | Loki | In-game chat commands + `!mp` / `!pool` / `!clan` / `!season` sets |
| `migrations/` | Shared | `hinaDir_admin_v2.sql` is Hina-owned; `base.sql` + `migrations.sql` upstream |

## Build & Run

Dependency management is **UV** (Astral). Poetry is gone; `pyproject.toml` uses `[project.optional-dependencies]` + `[dependency-groups]` for UV semantics. Lockfile is `uv.lock`.

### Makefile Targets

```bash
# Install
make install          # uv sync --all-extras --dev
make uninstall        # rm -rf .venv (uv has no uninstall; wipe venv)

# Run
make build            # docker build -t bancho:latest .
make run              # docker compose up bancho mysql redis (foreground)
make run-bg           # docker compose up -d bancho mysql redis
make run-cfd          # docker-compose.cloudflared.yml variant
make run-cfd-bg       # ...detached
make run-caddy        # caddy run --envfile .env --config ext/Caddyfile
make logs [last=N]    # tail compose logs (default last=1)
make shell            # uv run python (interactive REPL)

# Test
make test             # spin up bancho-test/mysql-test/redis-test via docker-compose.test.yml and run scripts/run-tests.sh inside the container

# Lint / format
make lint             # uv run ruff check . --fix
make format           # uv run black . && uv run ruff check . --fix
make format-check     # uv run black . --check && uv run ruff check .

# Type checking (three backends; ty is primary)
make type-check       # uv run ty check . --exclude .venv --exclude tools --exclude tests
make type-check2      # uv run mypy .  (fallback)
make type-check3      # uv run pyright .  (alternative)

# Security
make security-check   # uv run bandit -r . -ll --exclude ".venv,venv,tests,testing,migrations,tools,__pycache__"

# Versioning
make bump version=patch   # uv run bump2version ... (DO NOT use without caution)
```

### Docker

- **Base image:** `python:3.11-slim` (`.python-version` pins `3.11`; `pyproject.toml` enforces `>=3.11,<3.12`).
- **Workdir:** `/srv/root`.
- **Package manager:** UV (copied from `ghcr.io/astral-sh/uv:latest` into `/bin/`).
- **System deps:** `nginx`, `git`, `curl`, `build-essential`, `default-mysql-client`, `redis-tools`.
- **Install:** `uv sync --frozen --no-dev` after copying `pyproject.toml` + `uv.lock` + `README.md`.
- **Entrypoint:** `scripts/start_server.sh`.

Startup sequence (`scripts/start_server.sh`):
1. `scripts/install-nginx-config.sh` — generate `web.conf` from `DOMAIN`.
2. `scripts/wait-for-it.sh --timeout=60 $DB_HOST:$DB_PORT` — block on MySQL TCP.
3. `scripts/wait-for-it.sh --timeout=60 $REDIS_HOST:$REDIS_PORT` — block on Redis TCP.
4. `uv run python main.py` — boot uvicorn.

### Entry Point (`main.py`)

```python
uvicorn.run(
    "app.api.init_api:asgi_app",
    reload=app.settings.DEBUG_LEVEL >= 1,
    log_level=logging.WARNING,
    server_header=False,
    date_header=False,
    headers=[("bancho-version", app.settings.VERSION)],
    host=app.settings.APP_HOST,
    port=app.settings.APP_PORT,
)
```

`app.utils.display_startup_dialog()` runs before uvicorn. Logging is configured at import time via `app.logging.configure_logging()`.

## Project Structure

```
kawata.py/
  main.py                           # Entry (uvicorn runner) + startup dialog
  pyproject.toml                    # UV config, ruff, ty, mypy, bandit, pytest, isort
  uv.lock                           # UV lockfile (authoritative; frozen in Dockerfile)
  ty.toml                           # Ty type checker config
  .python-version                   # 3.11
  Dockerfile                        # python:3.11-slim + UV
  docker-compose.yml
  docker-compose.test.yml           # mysql-test / redis-test / bancho-test
  Makefile                          # uv-based make targets
  CODEOWNERS                        # * @TheFantasticLoki
  AGENTS.md                         # Quick agent cheat-sheet

  app/
    api/
      init_api.py                   # BanchoAPI class, lifespan, host-based routing, middlewares, exc handlers
      __init__.py                   # Assembles v1 + v2 routers into api_router
      middlewares.py                # MetricsMiddleware (per-request timing + logging)
      v1/
        __init__.py                 # apiv1_router (prefix=/v1) — mounts v1.api + hinaDir
        api.py                      # 21 endpoints (~1920 lines): calc_pp, players, scores, maps, matches, leaderboards, friends, badges, online sample
        hinaDir/
          __init__.py
          friends.py                # 6 endpoints: friends_detailed/status, set_relationship, friends_leaderboard, player_quick_stats, compare_stats
          pp_records.py             # 1 endpoint: get_pp_records (cheat filter)
      v2/
        __init__.py                 # apiv2_router (prefix=/v2) — mounts clans, client, maps, players, scores, seasons
        clans.py                    # GET /clans, /clans/{id}
        client.py                   # GET /changelog
        maps.py                     # GET /maps, /maps/{id}
        players.py                  # GET /players, /players/{id}, status, stats/{mode}, stats
        scores.py                   # GET /scores, /scores/{id}
        seasons.py                  # Seasons + schedules + preference CRUD (12 endpoints)
        common/
          json.py                   # ORJSONResponse + Pydantic-aware dumps
          responses.py              # Success[T] / Failure wrappers
        models/                     # Pydantic v2 response models
          clans.py, maps.py, players.py, scores.py, seasons.py, __init__.py
      domains/
        cho.py                      # Bancho binary protocol — ~80+ packet handlers
        osu.py                      # Score submission, /users, screenshots, direct search, seasonal BG, error reporting
        map.py                      # Beatmap redirect -> b.ppy.sh
        packets/
          common.py                 # @register / @register_restricted decorators
          aeris.py                  # Aeris client extensions (IDENTIFY, CREATE_GROUP, INVITE_GROUP, …)

    constants/
      privileges.py                 # Privileges IntFlag, ClientPrivileges, ClanPrivileges, GetPriv()
      gamemodes.py                  # GameMode IntEnum (0-11), from_params(), valid_gamemodes, as_vanilla
      mods.py                       # Mods IntFlag (31 flags), filter_invalid_combos(), from_modstr, from_np
      regexes.py                    # Usernames, emails, osu! versions, mappool picks, BO series
      clientflags.py                # ClientFlags + LastFMFlags (anticheat, hack detection)
      aeris_features.py             # AerisFeatures — bitwise feature flags for Aeris client

    objects/
      player.py                     # Player (status, stats, friends, blocks, enqueue, privileges)
      beatmap.py                    # Beatmap + BeatmapSet, API fetch, cache, RankedStatus
      score.py                      # Score, grade calc, SubmissionStatus
      match.py                      # Multiplayer match (slots, teams, freemods, win conditions)
      channel.py                    # Chat channels with priv-gated read/write
      collections.py                # Players / Channels / Matches / Groups + initialize_ram_caches()
      group.py                      # Aeris user groups
      achievement.py                # Achievement objects + condition AST
      badge.py / badge_style.py     # Badge system
      models.py                     # Shared model definitions

    repositories/                   # Base data access layer (users, scores, stats, maps, clans, channels, badges, logs, achievements, user_achievements, comments, ratings, favourites, client_hashes, ingame_logins, mail, map_requests, tourney_pools, tourney_pool_maps, seasons)
      __init__.py                   # SQLAlchemy mapper_registry + Base
      users.py                      # READ_PARAMS, User TypedDict, create/fetch_one/fetch_many/partial_update
      scores.py                     # ScoresTable + ScoreInfoTable
      stats.py                      # Per (user, mode, season_id) row
      maps.py                       # Beatmap DB with RankedStatus
      clans.py, channels.py, badges.py, logs.py, comments.py, ratings.py,
      favourites.py, achievements.py, user_achievements.py, client_hashes.py,
      ingame_logins.py, mail.py, map_requests.py, tourney_pools.py,
      tourney_pool_maps.py, seasons.py
      hinaDir/
        admin_logs.py               # Admin V2 logging (0=user, 1=map, 2=badge)
        work_items.py               # Beatmap review work items
        review_comments.py          # Review comment threads

    state/
      services.py                   # Globals: database, redis, http_client, ip_resolver, datadog. run_sql_migrations, fetch_geoloc, IPResolver, Version parser, strange_occurrence logger
      sessions.py                   # players, channels, groups, matches, api_keys (dict), housekeeping_tasks, bot
      cache.py                      # bcrypt, beatmap, beatmapset, unsubmitted, needs_update
      __init__.py                   # Module-level loop reference + packet handler registry

    usecases/
      performance.py                # ScoreParams, PerformanceRating, DifficultyRating, calculate_performances()
      achievements.py               # Achievement eval (safe AST, no eval())
      user_achievements.py          # Per-user achievement tracking

    schedule_types/                 # Season schedule providers (used by seasons system)
      base.py                       # ScheduleTypeProvider abstract base
      manual.py                     # Admin-controlled start/end
      standard_calendar.py          # custom, half_year, third_year, quarter_year
      seasonal.py                   # Spring/Summer/Fall/Winter
      international_fixed_calendar.py  # 28-day month IFC
      __init__.py                   # get_provider_for_schedule_type()

    adapters/
      database.py                   # Database wrapper: SQLAlchemy compilation, MySQLDialect, debug timing, MySQLError swallowing

    bg_loops.py                     # Housekeeping tasks (donor expiry, ghost DC, bot status, season checker, stats updater)
    commands.py                     # In-game chat commands (~2.9k lines) — regular + mp/pool/clan/season CommandSets
    discord.py                      # Webhook client (Embed, Footer, Image, Thumbnail, Author, Field) — tenacity retry
    encryption.py                   # py3rijndael helpers (score encryption)
    logging.py                      # Ansi, logLevel, DebugFilter, log(), error_catcher, StructlogFormatter, IPResolver
    packets.py                      # ClientPackets enum + server packet builders (login_reply, notification, user_stats, …)
    settings.py                     # All env config (dotenv-loaded)
    settings_utils.py               # read_bool, read_list
    timer.py                        # Performance timing context manager
    utils.py                        # make_safe_name, ensure_persistent_volumes_are_available, download_default_avatar, achievement image downloader, DebugLevelWatcher
    _typing.py                      # IPAddress, UNSET sentinel

  migrations/
    base.sql                        # Initial schema (~27 KB)
    migrations.sql                  # Incremental updates with `# v{X.Y.Z}` headers (~33 KB, through v5.3.2)
    hinaDir_admin_v2.sql            # Admin V2 tables — standalone

  scripts/
    start_server.sh                 # Docker entrypoint (nginx + wait-for + uv run python main.py)
    install-nginx-config.sh         # Generate nginx web.conf from DOMAIN
    wait-for-it.sh                  # TCP wait utility
    run-tests.sh                    # pytest harness used by docker-compose.test.yml
    fix-multipart.sh                # Deprecated multipart patch (retained)

  tools/
    recalc.py                       # PP recalculation script
    proxy.py                        # mitmproxy helper
    migrate_logs.py                 # Legacy logs → new schema migrator
    parse_bandit.py                 # bandit JSON → GitHub step summary
    enable_geoip_module.sh          # nginx GeoIP module helper
    generate_cf_dns_records.sh      # Cloudflare DNS helper
    local_cert_generator.sh         # Dev self-signed certs
    migrate_v420/                   # Go-based 4.2.0 migration tool
    ci/                             # CI orchestration (see §CI)
      ci.py
      core/                         # cli, config, context, errors, logging, storage
      modules/
        artifacts/artifacts.py
        parsers/                    # registry.py + bandit/generic/mypy/pytest/ruff/safety/trivy/ty parsers
        report/report.py
        summary/summary.py
        workflow/workflow.py
      storage/artifact_backend.py
      templates/                    # Jinja2 — ci_report.md, workflow_summary.md
      scripts/ci-bootstrap.sh
      utils/                        # github, timing

  tests/
    conftest.py                     # Pytest fixtures (asgi-lifespan app, httpx client, respx auto-mock, structlog setup)
    unit/
      packets_test.py               # Binary packet serialization
      ci/                           # test_cli, test_context, test_parsers, conftest
    integration/
      domains/osu_test.py           # Score submission integration

  testing/
    sample_data/                    # Fixture data used by tests

  .env.example                      # All config variables
  .github/workflows/
    ci.yaml                         # Unified pipeline: initialization → build → (mypy, ruff, ty, bandit, test) → release → publish → final-summary
    build.yaml
    sync-docs.yaml
    old/                            # Archived: 1-master, build, lint, prep-build, publish, release, sec-scan, summarize, test
  ext/                              # Caddyfile + nginx.conf.example
  plans/                            # Design docs (01-09 + README) — logs overhaul, seasons, clans, cosmetics, donor, score hunts, sessions, api/migration
  logging.yaml.example              # Stdlib logging config template
```

## Configuration (`app/settings.py`)

All settings loaded from `.env` via `python-dotenv`. VERSION is parsed from `pyproject.toml` via `tomllib` at import time.

### Required (hard-crash if unset)

| Variable | Purpose | Example |
|----------|---------|---------|
| `APP_HOST` | Bind address | `0.0.0.0` |
| `APP_PORT` | Bind port | `10000` |
| `SERVICE_NAME` | Logging identifier | `kawata` |
| `CONTAINER_NAME` | Docker container name | `bancho` |
| `CHEAT_SERVER` | Enable cheat server features | `False` |
| `DOMAIN` | Server domain | `kawata.example.com` |
| `USINGROOTDOMAIN` | Accept osu requests on root domain | `False` |
| `DB_HOST/PORT/USER/PASS/NAME` | MariaDB connection | `mysql:3306/cmyui/lol123/banchopy` |
| `REDIS_HOST/PORT/USER/PASS/DB` | Redis connection | `redis:6379/default//0` |
| `MIRROR_SEARCH_ENDPOINT` | Beatmap search mirror | `https://catboy.best/api/search` |
| `MIRROR_DOWNLOAD_ENDPOINT` | Beatmap download mirror | `https://catboy.best/d` |
| `COMMAND_PREFIX` | In-game command prefix | `!` |
| `REQUEST_PENDING_ONLY` | `!requests` shows only pending maps | `True` |
| `SEASONAL_BGS` | Main-menu background image list | comma-separated URLs |
| `MENU_ICON_URL` | In-game menu banner icon | URL |
| `MENU_ONCLICK_URL` | Banner click target | URL |
| `DATADOG_API_KEY` / `DATADOG_APP_KEY` | Optional Datadog | empty or key |
| `DEBUG_LEVEL` | 0=INFO, 1=DBGLV1, 2=DBGLV2, 3=VERBOSE | `0` |
| `DEBUG_FOCUS` | Filter scope (`all`, `db`, …) | `all` |
| `REDIRECT_OSU_URLS` | Forward beatmap pages to osu.ppy.sh | `True` |
| `PP_CACHED_ACCS` | Accuracies cached for calc endpoints | `90,95,98,99,100` |
| `DISALLOWED_NAMES` | Blocked usernames | comma-separated |
| `DISALLOWED_PASSWORDS` | Blocked passwords | comma-separated |
| `DISALLOW_OLD_CLIENTS` | Reject outdated clients | `True` |
| `DISALLOW_INGAME_REGISTRATION` | Block in-game signup | `True` |
| `DISCORD_AUDIT_LOG_WEBHOOK` | Audit log webhook URL | — |
| `DISCORD_INVITE` | Invite URL (shown in-game) | `https://discord.gg/...` |
| `AUTOMATICALLY_REPORT_PROBLEMS` | Share bugs with cmyui | `False` |
| `LOG_WITH_COLORS` | ANSI colors in console | `False` |
| `DEVELOPER_MODE` | Dangerous dev features | `False` |

### Optional

| Variable | Purpose |
|----------|---------|
| `OSU_API_KEY` | Official osu! API key (beatmap metadata fetch) — set via env, `None` if empty |
| `BOT_API_KEY` | Internal auth key for kawaweb → kawata.py (admin writes). `None` if empty |
| `CLIENT_VERSION` | Hosting a specific client version (cheat server mode) |

### Derived

```python
DB_DSN    = f"mysql://{DB_USER}:{quote(DB_PASS)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
REDIS_DSN = f"redis://{REDIS_USER}:{quote(REDIS_PASS)}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"  # auth segment omitted if either user or pass is empty
VERSION   = tomllib.load(open('pyproject.toml','rb'))['project']['version']  # currently 5.3.2
```

### `.env.example` extras (not consumed by `app/settings.py` — used by docker-compose / CI)

`TZ`, `CONTAINER_VERSION`, `GITHUB_OWNER`, `GITHUB_REPO`, `DATA_DIRECTORY`, `SSL_CERT_PATH`, `SSL_KEY_PATH`, `TUNNEL_TOKEN`, `MMD_DB_PATH` (MaxMind GeoIP DB path, commented out).

## Architecture

### Host-Based Request Routing (`app/api/init_api.py`)

The server uses Starlette's `app.host()` to dispatch by subdomain. Routes are registered for BOTH `ppy.sh` (for osu! client direct) AND the configured `DOMAIN`:

```python
for domain in ("ppy.sh", app.settings.DOMAIN):
    for subdomain in ("c", "ce", "c4", "c5", "c6"):
        asgi_app.host(f"{subdomain}.{domain}", domains.cho.router)   # Bancho binary protocol
    asgi_app.host(f"osu.{domain}", domains.osu.router)               # Score submission, /users, screenshots
    if app.settings.USINGROOTDOMAIN:
        asgi_app.host(f"{domain}", domains.osu.router)               # Root domain -> osu
    asgi_app.host(f"b.{domain}", domains.map.router)                 # Beatmap redirect
    asgi_app.host(f"api.{domain}", api_router)                       # REST API (v1 + v2)
```

**Critical:** Requests to the API MUST have `Host: api.{domain}` set. Direct calls (`http://bancho:10000/v1/...`) without the Host header return 405 — that is the #1 source of cross-service integration bugs with kawaweb.

Domain routers are additionally `include_router`'d on the top-level app so they show up in OpenAPI via the custom `BanchoAPI` subclass (see `openapi()` override).

### Application Lifespan (`init_api.py:lifespan`)

Startup:
1. Reconfigure stdout encoding to UTF-8 (Windows-friendly).
2. `app.utils.ensure_persistent_volumes_are_available()` — mkdir `.data/{avatars,logs,osu,osr,ss}`, download achievement images + default avatar.
3. `app.state.loop = asyncio.get_running_loop()`.
4. Warn if running as root.
5. `database.connect()` — open MySQL pool.
6. `redis.initialize()` — connect Redis.
7. Start Datadog (only if `DATADOG_API_KEY` + `DATADOG_APP_KEY` set).
8. `app.state.services.ip_resolver = IPResolver()`.
9. `run_sql_migrations()` — apply `migrations/migrations.sql` since last `startups` row.
10. `collections.initialize_ram_caches()` — load channels, groups, achievements, clans, ensure BanchoBot exists.
11. `bg_loops.initialize_housekeeping_tasks()` — spawn background tasks.
12. Log `Listening @ {APP_HOST}:{APP_PORT}`.

Shutdown:
1. `sessions.cancel_housekeeping_tasks()`.
2. `http_client.aclose()`, `database.disconnect()`, `redis.aclose()`.
3. Datadog `stop()` + `flush()`.

### Middleware Stack

1. **`MetricsMiddleware`** (`app/api/middlewares.py`) — logs every request with method, URL, status, process time, headers, client IP/country; emits `X-Process-Time` header.
2. Inline **`http_middleware`** (in `init_api.py`) — catches `ClientDisconnect` and `RuntimeError("No response returned.")` mid-request, returning `"Client is stupppod"` so the server doesn't explode on cancelled leaderboard fetches.

### Exception Handlers

- `RequestValidationError` → pretty-print validation errors + `ORJSONResponse` 422.

### State Management

**Global services** (`app/state/services.py`):
- `database: Database` — `app.adapters.database.Database` over `databases` + SQLAlchemy query compilation.
- `redis: aioredis.Redis` — from `REDIS_DSN`.
- `http_client: httpx.AsyncClient`.
- `ip_resolver: IPResolver` — CF + nginx header priority with in-memory LRU.
- `datadog: ThreadStats | None` — optional.

**In-memory sessions** (`app/state/sessions.py`):
- `players: Players` — online player collection.
- `channels: Channels` — active chat channels.
- `matches: Matches` — 64-slot multiplayer matches.
- `groups: Groups` — Aeris user groups.
- `api_keys: dict[str, int]` — `{api_key: user_id}` cache.
- `housekeeping_tasks: set[asyncio.Task]` — bg task handles.
- `bot: Player` — BanchoBot reference.

**Caches** (`app/state/cache.py`):
- `bcrypt: dict[bytes, bytes]` — `{bcrypt_hash: md5_hash}` (avoid re-hashing known passwords).
- `beatmap: dict[str | int, Beatmap]` — by md5 or ID.
- `beatmapset: dict[int, BeatmapSet]`.
- `unsubmitted: set[str]` — known unsubmitted md5s.
- `needs_update: set[str]` — maps needing metadata refresh.

### Background Tasks (`app/bg_loops.py`)

| Task | Interval | Purpose |
|------|---------:|---------|
| `_remove_expired_donation_privileges` | 30 min | Revoke `DONATOR` from expired rows, enqueue notification |
| `_disconnect_ghosts` | ~100 s (`OSU_CLIENT_MIN_PING_INTERVAL / 3`) | Drop idle clients past 300s ping threshold |
| `_update_bot_status` | 5 min | Clear `bot_stats` packet cache (BanchoBot status rotation) |
| `DebugLevelWatcher.watch` | 1 s | Runtime `DEBUG_LEVEL` adjustments without restart |
| `check_season_schedules` | 60 s | Auto-rotate seasons / retroactive creation when no seasons exist yet |
| `update_non_active_season_stats` | 5 min | Update historical-season stats with exponential-backoff retry |

All tasks are created via `loop.create_task(...)` and stored in `sessions.housekeeping_tasks`; cancelled in shutdown.

### Database Adapter (`app/adapters/database.py`)

Wraps `databases` library:
- SQLAlchemy `ClauseElement` compilation via a custom `MySQLDialect` (named paramstyle).
- Methods: `fetch_one`, `fetch_all`, `fetch_val`, `execute`, `execute_many`, `transaction`, `ping`.
- `MySQLError` is caught, logged with query + params, and returns `None` (NON-throwing). **This means a failed `fetch_all` or `execute` is silent** — always check return value or look at logs.
- Debug-level query timing via `app.timer.Timer` when `DEBUG_LEVEL >= 2`.

### Repository Pattern

Each repository module has:
1. `Table(Base)` — SQLAlchemy declarative table definition.
2. `READ_PARAMS: tuple[Column, ...]` — columns selected by default.
3. `TypedDict` for the return row shape (e.g. `User`, `Score`, `Map`, `Clan`).
4. Async CRUD: `create`, `fetch_one`, `fetch_count`, `fetch_many`, `partial_update`, often `delete`.
5. All queries go through `app.state.services.database.*`.

Base repositories: `users`, `scores` (`ScoresTable` + `ScoreInfoTable`), `stats` (composite key `(id, mode, season_id)` as of v5.3.2), `maps`, `clans`, `channels`, `badges`, `logs`, `achievements`, `user_achievements`, `comments`, `ratings`, `favourites`, `client_hashes`, `ingame_logins`, `mail`, `map_requests`, `tourney_pools`, `tourney_pool_maps`, `seasons`.

hinaDir repositories: `admin_logs`, `work_items`, `review_comments`.

## API Reference

All endpoints mounted under `api.{domain}/`. Responses use `ORJSONResponse` (v1) or `Success[T] / Failure` wrappers via `app/api/v2/common/responses.py` (v2).

### v1 Endpoints — `/v1/...`

All routes in `app/api/v1/api.py`. Public unless otherwise noted.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/calculate_pp` | API key | PP calc for a single map; `acc` list OR `n300/n100/n50/ngeki/nkatu` |
| GET | `/calculate_pp_batch` | API key | Batch PP for multiple beatmap IDs |
| GET | `/search_players` | — | Search by name; returns ascending-ID list |
| GET | `/get_player_count` | — | Online + total registered + total scores + recent users |
| GET | `/get_player_info` | — | Detailed profile (`scope=info|stats|all`) |
| GET | `/get_player_status` | — | Current online status if any |
| GET | `/get_player_scores` | — | Recent / best scores |
| GET | `/get_player_most_played` | — | Most-played beatmaps |
| GET | `/get_map_info` | — | Beatmap metadata by id/md5/set |
| GET | `/get_map_scores` | — | Top scores for a map |
| GET | `/get_score_info` | — | Single score details |
| GET | `/get_replay` | — | Download replay (with/without headers) |
| GET | `/get_match` | — | Multiplayer match snapshot |
| GET | `/get_leaderboard` | — | Global / country leaderboards |
| GET | `/get_top_players` | — | Top 3 per mode |
| GET | `/get_clan` | — | Clan details by id/name/tag |
| GET | `/get_mappool` | — | Tournament pool by id/name |
| GET | `/get_friends` | — | User's friend ID list |
| GET | `/get_badges` | — | Badge listing |
| POST | `/update_map_status` | BOT_API_KEY | Change beatmap ranked status (invalidates caches) |
| GET | `/get_online_players_sample` | — | Random sample of online players (id, name, country, clan, pp, rank, status) — in-memory only |

### v1 hinaDir — `/v1/...`

**`app/api/v1/hinaDir/friends.py`**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/get_friends_detailed` | — | Friends / followers / blocked with online status. `scope=mutuals|followers|blocked|all` |
| GET | `/get_friends_status` | — | Lightweight online-status poll |
| POST | `/set_relationship` | BOT_API_KEY | `action=add_friend|remove_friend|block|unblock` |
| GET | `/get_friends_leaderboard` | — | Mutual friends + self, ranked by PP |
| GET | `/get_player_quick_stats` | — | Stats + top play for a single user |
| GET | `/compare_stats` | — | Side-by-side stats for 2-4 players |

**`app/api/v1/hinaDir/pp_records.py`**

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/get_pp_records` | — | PP records, optional `cheat_type`/`min`/`max` filters |

### v2 Endpoints — `/v2/...`

RESTful CRUD with pagination; `Success[T]` / `Failure` response wrappers (see `common/responses.py`) backed by `ORJSONResponse` (see `common/json.py`). All Pydantic models live under `app/api/v2/models/`.

**`players.py`**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/players` | Paginated player list |
| GET | `/players/{player_id}` | Single player |
| GET | `/players/{player_id}/status` | Online status |
| GET | `/players/{player_id}/stats/{mode}` | Stats for one mode |
| GET | `/players/{player_id}/stats` | Stats all modes |

**`scores.py`**: `GET /scores`, `GET /scores/{score_id}`
**`maps.py`**: `GET /maps`, `GET /maps/{map_id}`
**`clans.py`**: `GET /clans`, `GET /clans/{clan_id}`
**`client.py`**: `GET /changelog`

**`seasons.py`** (new in v5.3.2):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/seasons` | List seasons |
| GET | `/seasons/{season_id}` | Single season |
| GET | `/seasons/{season_id}/stats` | Aggregate stats for a season |
| GET | `/players/{player_id}/season-preference` | Player's chosen leaderboard view |
| POST | `/players/{player_id}/season-preference` | Update preference |
| GET | `/schedules` | List schedules |
| GET | `/schedules/{schedule_id}` | Single schedule |
| GET | `/schedules/{schedule_id}/active-season` | Current season for that schedule |
| PUT | `/players/{player_id}/preferred-schedule` | Update player's preferred schedule |
| GET | `/players/{player_id}/preferred-schedule` | Fetch player's preferred schedule |

### Domain Handlers

- **`cho.py`** — Bancho binary protocol. ~80+ packet handlers (login, spectator, multiplayer, chat, presence, friends, channels, tournament). `BanchoPacketReader` reads client packets; `app/packets.py` builds server packets. Registered via `@register` decorator in `app/api/domains/packets/common.py`. Aeris extensions live in `app/api/domains/packets/aeris.py` (IDENTIFY, CREATE_GROUP, ACCEPT_GROUP, INVITE_GROUP, GROUP_KICK, GROUP_LEAVE, GROUP_USERS, DISBAND_GROUP, CREATE_GROUP_MATCH / DISMOUNT_GROUP_MATCH (stubs)).
- **`osu.py`** — Score submission (`/web/osu-submit-modular-selector.php`), screenshots, `/users` registration, seasonal BG rotation, direct search, leaderboards, error reporting.
- **`map.py`** — Redirects to `b.ppy.sh`.

## Constants

### Privileges (`app/constants/privileges.py`)

`Privileges(IntFlag)` stored in `users.priv`:

| Val | Name | Val | Name |
|-----|------|-----|------|
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
- `NOMINATOR` = `ManageBeatmaps | AccessPanel`
- `SUPPORT` = `BanUsers | SilenceUsers | WipeUsers | KickUsers | ChatMod | ViewPanelLog | SendAlerts | ManageClans | AccessPanel`
- `MODERATOR` = `SUPPORT | ManageUsers | ManageBadges | ViewSensitiveInfo`
- `ADMINISTRATOR` = `MODERATOR | ManagePrivs`
- `DONATOR` = `SUPPORTER | PREMIUM`
- `STAFF` = `NOMINATOR | SUPPORT | MODERATOR | ADMINISTRATOR | DEVELOPER`

**Checking pattern:**
```python
# Has ALL privs in a group:
if user_priv & Privileges.MODERATOR == Privileges.MODERATOR: ...

# Has ANY priv in a group:
if user_priv & Privileges.STAFF: ...
```

**Helpers:**
- `GetPriv(int) -> list[Privileges]` — decompose int into flag list.
- `GetPriv(list[Privileges]) -> int` — combine flags into int.

**ClientPrivileges** (sent to osu! client for in-game UI): `PLAYER, MODERATOR, SUPPORTER, OWNER, DEVELOPER, TOURNAMENT`.

**ClanPrivileges** (IntEnum): `Member=1, Officer=2, Owner=3`.

### Game Modes (`app/constants/gamemodes.py`)

```
0 VANILLA_OSU      4 RELAX_OSU      8 AUTOPILOT_OSU
1 VANILLA_TAIKO    5 RELAX_TAIKO    9 AUTOPILOT_TAIKO (unused)
2 VANILLA_CATCH    6 RELAX_CATCH   10 AUTOPILOT_CATCH (unused)
3 VANILLA_MANIA    7 RELAX_MANIA   11 AUTOPILOT_MANIA (unused)
               (unused)
```

- `GameMode.from_params(mode_vn, mods)` → adds 4 for RX, 8 for AP.
- `GameMode.valid_gamemodes()` — cached list, excludes 7, 9, 10, 11.
- `mode.as_vanilla` → `value % 4`.
- `repr(mode)` → string like `"vn!std"`, `"rx!taiko"`, `"ap!std"`.

### Mods (`app/constants/mods.py`)

`Mods(IntFlag)` — 31 flags (NOMOD, NOFAIL, EASY, TOUCHSCREEN, HIDDEN, HARDROCK, SUDDENDEATH, DOUBLETIME, RELAX, HALFTIME, NIGHTCORE, FLASHLIGHT, AUTOPLAY, SPUNOUT, AUTOPILOT, PERFECT, KEY4-KEY9, KEY1-KEY3, KEYCOOP, FADEIN, RANDOM, CINEMA, TARGET, SCOREV2, MIRROR).

Utilities:
- `filter_invalid_combos(mode_vn)` — strips DT when NC present, drops HR when EZ present, strips SD/PF for NF/RX/AP, strips mode-specific mods from other modes, trims duplicate KEY mods.
- `from_modstr("HDDTRX")` — LRU-cached parser, 2-char chunks.
- `from_np(s, mode_vn)` — parse `/np`-style strings.
- `get_mods_string(mods)` — readable output.
- Constants: `SPEED_CHANGING_MODS = DT | NC | HT`, `KEY_MODS = KEY1..KEY9`, `OSU_SPECIFIC_MODS`, `MANIA_SPECIFIC_MODS`.

### ClientFlags (`app/constants/clientflags.py`)

`ClientFlags(IntFlag)` + `LastFMFlags(IntFlag)` — anticheat flags reported by client (speed hacks, checksum failures, HQ AssemblyResolver, etc.).

### Regexes (`app/constants/regexes.py`)

Compiled patterns for usernames, emails, osu! client versions, mappool picks, best-of series — used throughout input validation, registration, tournament parsing.

### AerisFeatures (`app/constants/aeris_features.py`)

Bitwise feature flags for the Aeris client: `None_=0, Groups=1<<0, Cheats=1<<1, All=~0`.

## In-Game Commands (`app/commands.py`)

Triggered by `COMMAND_PREFIX` (default `!`). Structure:

- `Command(NamedTuple)` — `triggers`, `callback`, `priv`, `hidden`, `doc`.
- `CommandSet` — grouped commands registered via `@cmd_set.add(priv, aliases, hidden)`.
- `Context(dataclass)` — `player`, `trigger`, `args`, `recipient`.
- Global `regular_commands: list[Command]` registered via `@command(priv, ...)`.
- `command_sets = [mp_commands, pool_commands, clan_commands, season_commands]`.

### Regular commands (by priv)

- **UNRESTRICTED:** `help`/`h`, `roll`, `block`, `unblock`, `reconnect`, `maplink`, `recent`/`last`/`r`, `top`, `_with`/`w` (np-based mod query), `request`/`req`, `apikey`, `server`, `pingme` (via commands), mirror helpers (`bloodcat`/`beatconnect`/`chimu`/`q`).
- **SUPPORTER:** `changename`.
- **NOMINATOR:** `requests`/`reqs`, `_map` (rank/unrank/love via status_to_id).
- **MODERATOR:** `notes`, `addnote`, `silence`, `unsilence`.
- **ADMINISTRATOR:** `user`/`u`, `restrict`, `unrestrict`, `alert`, `alertuser`/`alertu`, `switchserv`, `shutdown` (with server= command context).
- **DEVELOPER:** `stealth`, `recalc`, `debug`, `debug_focus`, `addpriv`, `rmpriv`, `givedonator`, `wipemap`, `reload`/`re`.

### `!mp` — multiplayer set

`help`/`h`, `start`/`st`, `abort`/`a`, settings mutators, `mods`/`fm`/`fmods`, `host`, `invite`/`inv`, `lock`, `unlock`, `team`, `map`, `password`, `ref`, `condition`/`cond`, `autoref`, `endmatch`/`end`, `removeref`/`rm`, `force`/`f` (ADMIN), `loadpool`/`lp`, `unloadpool`/`ulp`, `start_timer`, `clearhost`, `size`.

### `!pool` — tournament mappool (TOURNEY_MANAGER)

`help`/`h`, `create`/`c`, `delete`/`del`/`d`, `add`/`a`, `remove`/`rm`/`r`, `list`/`l`, `info`/`i`.

### `!clan` — clan management

`help`/`h`, `create`/`c`, `delete`/`delete`/`d`, `info`/`i`, `leave`, `list`/`l`.

### `!season` — season management (ADMINISTRATOR + a public one)

6 sub-commands: schedule introspection, manual start/end, stats recalc, user-visible `!season` query (UNRESTRICTED).

## PP Calculator (`app/usecases/performance.py`)

Uses **akatsuki-pp-py 1.0.0** (Rust-backed Python binding; source builds disabled via `[tool.uv] no-build-package = ["akatsuki-pp-py"]`).

```python
@dataclass
class ScoreParams:
    mode: int
    mods: int | None = None
    combo: int | None = None
    acc: float | None = None                  # OR n300/n100/n50/ngeki/nkatu/nmiss — not both
    n300 / n100 / n50 / ngeki / nkatu / nmiss: int | None = None

class PerformanceRating(TypedDict):
    pp, pp_acc, pp_aim, pp_speed, pp_flashlight, effective_miss_count, pp_difficulty

class DifficultyRating(TypedDict):
    stars, aim, speed, flashlight, slider_factor, speed_note_count, stamina, color, rhythm, peak

class PerformanceResult(TypedDict):
    performance: PerformanceRating
    difficulty: DifficultyRating

def calculate_performances(osu_file_path: str, scores: Iterable[ScoreParams]) -> list[PerformanceResult]
```

**Rules:**
- Passing BOTH `acc` AND any hit-count field → `ValueError`.
- NC implies DT — code force-adds DT flag when NC is present (rosu-pp ignores NC).
- `NaN` / `Inf` PP is clamped to `0.0` (silent fallback — `TODO: report to logserver`).

## Logging System (`app/logging.py`)

Custom structured logger over stdlib + structlog + python-json-logger.

### Log levels (`logLevel(IntEnum)`)

| Level | Value | Notes |
|-------|------:|-------|
| DEBUG | 10 | stdlib |
| VERBOSE | 11 | custom |
| DBGLV2 | 14 | custom |
| DBGLV1 | 16 | custom |
| INFO | 20 | stdlib |
| WARNING | 30 | stdlib |
| ERROR | 40 | stdlib |
| CRITICAL | 50 | stdlib |

Custom names registered via `logLevel.add_Log_Levels()` (also into `structlog.stdlib.NAME_TO_LEVEL`).

### `log()` function

```python
def log(msg, start_color=None, extra=None, logger="", level=logging.INFO, levelow=False, exc_info=False, *args) -> None
```

- Routes to `console.info / .warn / .error / .debug` based on `Ansi` color + level.
- Adds `@timestamp`, `Message`, calling function info to `extra`.
- At level ≥ 21: adds stack trace, function args, local variables (serialized via `serialize_value`).
- At level ≥ 40: attaches `error_type`, `error_message`, full `traceback.format_exc()`, caller file/line/function.
- Supports `extra["filter"] = {"debugLevel": N, "debugFocus": "..."}` to gate log output (see `DebugFilter`).
- `LOG_WITH_COLORS=False` strips ANSI escapes from messages before emission (log-shipping-friendly).

### `DebugFilter`

`logging.Filter` that drops records whose `extra["filter"]["debugLevel"]` > `settings.DEBUG_LEVEL`, or whose `debugFocus` doesn't match `settings.DEBUG_FOCUS` (unless `DEBUG_FOCUS=all`). Attached to `console` logger + all console handlers.

### `error_catcher` decorator

Wraps async/sync functions, catches all exceptions, logs via `log(...)` with `original_traceback`, `exception_location`, `function_name`, `function_module` — then **re-raises**. (The old behavior of swallowing exceptions and returning `None` is gone — this is a recent change; endpoints decorated with `@error_catcher` now propagate errors through FastAPI's normal chain.)

### Formatters / handlers

- `BytesJsonFormatter` — sanitizes non-primitive keys/values, UTF-8 bytes output.
- `StructlogFormatter` — JSON output via configurable processors.
- `LogEncoder(JSONEncoder)` — circular-reference safe.
- `IPResolver` (module-level `ip_resolver` global) — `CF-Connecting-IP` → `X-Forwarded-For[0]` → `X-Real-IP` → `127.0.0.1` fallback, with caching.

Configuration from `logging.yaml` (or `LOG_CFG` env path) via `setup_logging()` + `setup_structlog()` at import time (`configure_logging()` called from `main.py`).

**Optional log shipping:** `python-logstash==0.4.8` is installed as a dependency for forwarding handlers configured in `logging.yaml`. (Elasticsearch is no longer a direct dependency.)

## Migration System

Version-based, applied automatically during lifespan startup (`run_sql_migrations` in `app/state/services.py`).

Files:
- `migrations/base.sql` — initial schema (`docker-entrypoint-initdb.d` style for fresh DBs).
- `migrations/migrations.sql` — incremental updates, `# v{X.Y.Z}` headers. Latest header: `# v5.3.2`.
- `migrations/hinaDir_admin_v2.sql` — standalone Admin V2 tables.

How it works:
1. Read latest version from `startups` table.
2. If no row, insert the current `pyproject.toml` version and return (first boot).
3. Parse `migrations.sql` by `# v{X.Y.Z}` headers and execute every query where `last_version < update_ver <= software_version`.
4. Multi-line SQL joined with spaces; queries terminated by `;`.
5. Failures raise `KeyboardInterrupt` — halts startup.

**CRITICAL rules:**
- Use `#` comments ONLY, never `--`. The runner joins multi-line SQL into a single line; `--` then comments out everything downstream.
- No transaction wrapping (MySQL DDL auto-commits).
- Migrations must remain idempotent-ish (guard with `IF NOT EXISTS`/`IF EXISTS` where possible).

### Notable recent migrations (v5.3.1 / v5.3.2)

- **v5.3.1:** `logs` table overhaul — drops legacy SHA256-id schema, rebuilds to admin_v2 layout (`id INT AUTO_INCREMENT`, `from_id`, `to_id`, `action`, `msg`, `created_at`, `action_type` with 0=user/1=map/2=badge). Drops legacy `users_ordr`. Drops `r_replay_id` from `scores` and `wiped_scores`.
- **v5.3.2:** Seasons system — new `seasons` and `season_schedules` tables. `stats` PK changes to `(id, mode, season_id)` (all-time = `season_id=0`). `users` gets `preferred_lb_view` + `preferred_schedule_id`. Gated behind `server_data.seasons_enabled` feature flag.

## Authentication

### API Authentication

HTTPBearer via `fastapi.security.HTTPBearer(auto_error=False)`, `api_key_dependency = Depends(http_bearer_scheme)`.

Flow:
- v1 auth check: `app.state.sessions.api_keys.get(token.credentials)` → user_id or `None`.
- `/update_map_status` additionally requires the token equal `app.settings.BOT_API_KEY` (kawaweb → kawata admin path).

### BOT_API_KEY lifecycle

1. Set in environment (Doppler or `.env`).
2. kawata.py caches it via `users.api_key` for user id 1.
3. `sql/post_init.sql` (in the parent kawataFullStack repo) seeds `UPDATE users SET api_key='kawata-dev-key' WHERE id=1` for dev.
4. Missing from DB → all authenticated calls return 401.

### Bancho protocol authentication

Password flow: `bcrypt(md5(plaintext))`. Both server AND client must use this exact scheme — a mismatch gives "Password is incorrect." Login packet includes: username, password_md5, client info, UTC offset, display-city flag.

## Data Paths

All under `Path.cwd() / ".data"` (mounted at `/srv/root/.data` in Docker):

| Path | Contents |
|------|----------|
| `.data/osu/` | `{beatmap_id}.osu` files |
| `.data/osr/` | `.osr` replay files |
| `.data/avatars/` | User avatars (+ `default.jpg` auto-downloaded at startup) |
| `.data/ss/` | Screenshots |
| `.data/assets/medals/client/` | Achievement images (auto-downloaded from `assets.ppy.sh`) |
| `.data/logs/` | Log files |
| `.data/logs/strange_occurrences/` | Pickled error objects (from `log_strange_occurrence`) |

`ensure_persistent_volumes_are_available()` creates all subdirs on startup and populates `default.jpg` + medals if missing.

## Redis Keys

| Key | Purpose |
|-----|---------|
| `bancho:leaderboard:{mode}` | Global PP leaderboard (sorted set) |
| `bancho:leaderboard:{mode}:{country}` | Country PP leaderboard |

Modes: 0-3 vanilla, 4-6 relax, 8 autopilot. Mode 7, 9, 10, 11 unused (see `GameMode.valid_gamemodes()`).

## Dependencies (from `pyproject.toml`)

### Runtime

| Package | Version | Purpose |
|---------|--------:|---------|
| `fastapi` | 0.109.2 | Web framework |
| `uvicorn` | 0.27.1 | ASGI server |
| `pydantic` | 2.6.1 | Validation |
| `databases[mysql]` | 0.8.0 | Async DB driver wrapper |
| `sqlalchemy` | ≥1.4.42,<1.5 | Query compilation |
| `redis[hiredis]` | 5.0.1 | Cache/sessions |
| `akatsuki-pp-py` | 1.0.0 | PP calc (Rust) |
| `bcrypt` | 4.1.2 | Password hashing |
| `orjson` | 3.11.6 | JSON |
| `py3rijndael` | 0.3.3 | Score encryption |
| `httpx` | 0.26.0 | Async HTTP client |
| `cryptography` | 46.0.5 | TLS / crypto |
| `tenacity` | 8.2.3 | Retry (Discord webhooks) |
| `structlog` | 24.1.0 | Structured logs |
| `python-json-logger` | 2.0.7 | JSON log formatter |
| `python-logstash` | 0.4.8 | Optional log forwarding |
| `datadog` | 0.48.0 | Optional metrics |
| `uvloop` | 0.19.0 (non-win) / `winloop` 0.1.1 | Fast event loop |
| `python-dotenv` | 1.0.1 | `.env` loader |
| `python-multipart` | 0.0.22 | Form parsing |
| `anyio` | 4.9.0 | |
| `psutil` | 5.9.8 | Process info |
| `py-cpuinfo` | 9.0.0 | CPU info |
| `timeago` | 1.0.16 | Relative time |
| `pytimeparse` | 1.1.8 | Parse durations |
| `requests` | 2.32.4 | Sync HTTP (legacy paths) |
| `pyyaml` | 6.0.1 | Config |
| `defusedxml` | ≥0.7.1 | Secure XML (ty/junit parsing) |
| `jsons` | 1.6.3 | Serialization |
| `python-rapidjson` | 1.17 | JSON (legacy) |
| `async-timeout` | 4.0.3 | |
| `tzdata` | 2024.1 | |
| `pytest` / `pytest-asyncio` / `asgi-lifespan` / `respx` / `coverage` | ... | Test runtime (packaged with runtime deps upstream) |

### Dev (`[project.optional-dependencies].dev`)

`pre-commit` 3.6.1, `black` 26.3.1, `isort` 5.13.2, `autoflake` 2.2.1, `mypy` 1.8.0, `ruff` 0.15.5, `ty` 0.0.29, `bandit` 1.9.4, `safety` 3.7.0, type stubs (`types-psutil`, `types-pymysql`, `types-requests`, `types-pyyaml`, `sqlalchemy2-stubs`).

### CI (`[dependency-groups].ci`)

`pyyaml` 6.0.1, `jinja2` ≥3.0.0, `defusedxml` ≥0.7.1. Installed in CI via `uv sync --only-group ci`.

## Code Style

- **Python:** 3.11 (exact). `requires-python = ">=3.11,<3.12"`.
- **Primary type checker:** `ty` (Astral's new type checker). Config in `ty.toml` — adds `tools/ci` to module search, ignores `unresolved-import`, `unresolved-attribute`, `deprecated`.
- **Fallback type checker:** `mypy` (strict + pydantic plugin) via `make type-check2`.
- **Alternative:** `pyright` via `make type-check3`.
- **Formatter:** `black` (via ruff format; `quote-style=double`, `indent-style=space`, `skip-magic-trailing-comma=false`, `docstring-code-format=true`).
- **Linter:** `ruff` (`target-version=py311`, fix=true). Selected rules: E/W/F/I/B/C4/UP. `E501` (line too long) ignored.
- **Import sorting:** via `isort` + ruff (`known-first-party=["app"]`; `add_imports=["from __future__ import annotations"]`, `force_single_line=true`, `profile="black"`).
- **Security:** `bandit` with skips for B101/B105/B324/B608.

**All files** start with `from __future__ import annotations` (isort injects automatically).

## Testing

```bash
make test                           # Docker-based: mysql-test + redis-test + bancho-test
# Single test (inside test container):
docker compose -f docker-compose.test.yml exec -T bancho-test pytest tests/path/to/test.py::test_name -v
```

- Pytest config: `asyncio_mode=auto`, `junit_suite_name=kawata-py`, `junit_log_passing_tests=true`, `junit_duration_report=call`.
- `tests/conftest.py` fixtures:
  - `mock_out_initial_image_downloads` (autouse) — `respx` mocks for default avatar + achievement images.
  - `app` — `LifespanManager` wrapping `asgi_app`.
  - `http_client` — `httpx.AsyncClient(app=app, base_url="http://test")`.
  - `configure_test_logging` (autouse, session) — structlog + stdlib console handler setup.
- Test layout:
  - `tests/unit/packets_test.py` — binary serialization.
  - `tests/unit/ci/` — `test_cli`, `test_context`, `test_parsers`, `conftest` (tests for `tools/ci/`).
  - `tests/integration/domains/osu_test.py` — score submission.
- Sample data: `testing/sample_data/`.

## Tools

### `tools/recalc.py`

PP recalculation tool. Connects to the configured DB, walks scores, recomputes PP via `akatsuki_pp_py`, writes back. Typically invoked manually / on-demand.

### `tools/proxy.py`

mitmproxy helper for intercepting osu! client traffic during debugging.

### `tools/migrate_logs.py`

One-shot migrator for the pre-v5.3.1 `logs` schema — converts SHA256-id legacy rows into the new auto-increment / `action_type` layout.

### `tools/parse_bandit.py`

Reads `bandit.json` and prints a GitHub `$GITHUB_STEP_SUMMARY`-friendly markdown table; exits 1 if any high/medium severity issue found.

### `tools/enable_geoip_module.sh`, `tools/generate_cf_dns_records.sh`, `tools/local_cert_generator.sh`

Shell helpers for nginx GeoIP setup, Cloudflare DNS record generation, and local dev self-signed certs.

### `tools/migrate_v420/`

Go module (`main.go`, `go.mod`) for a one-off 4.2.0 schema migration.

### `tools/ci/` — CI Orchestration (NEW in upstream BE-Dev)

Small composable CLI (`tools/ci/ci.py`) for tracking workflow lifecycle inside GitHub Actions and aggregating artifacts.

```
tools/ci/
  ci.py                       # CLI entry
  core/                       # cli, config, context, errors, logging, storage
  modules/
    workflow/workflow.py      # workflow start / finish
    summary/summary.py        # render per-job GITHUB_STEP_SUMMARY via Jinja2
    report/report.py          # cross-workflow aggregation
    artifacts/artifacts.py    # gather / normalize
    parsers/
      registry.py             # Parser ABC + register_parser/detect_parser/parse_file
      bandit_parser.py
      generic_parser.py
      mypy_parser.py
      pytest_parser.py        # JUnit XML
      ruff_parser.py
      safety_parser.py
      trivy_parser.py         # SARIF + JSON
      ty_parser.py             # NEW — Ty JUnit XML (uses defusedxml.ElementTree.fromstring)
  storage/
    artifact_backend.py       # ArtifactBackend (default)
  templates/
    ci_report.md
    workflow_summary.md
  scripts/ci-bootstrap.sh     # Bootstrap CI tool (called from workflows)
  utils/                      # github, timing
  requirements.txt            # pip-compatible (pyyaml, jinja2, defusedxml)
  README.md                   # Full CI tool docs
```

**Parser registry flow:** `detect_parser(file_path, content)` picks a parser by (1) filename stem (mypy/ruff/trivy/safety/bandit/junit/pytest/**ty**), (2) extension (`.xml` → pytest, `.sarif` → trivy), (3) JSON content heuristics. Unknown falls back to `generic`. Ty parser was added in the BE-Dev sync; it consumes `ty check --output-format junit` XML (parsed with `defusedxml` for safety).

**CLI shape:**
```bash
python tools/ci/ci.py [--storage artifact] [--config path] [--verbose] [--debug] [--json] \
    <workflow|summary|report|artifacts> <action> [args]
```

Modules: `workflow {start, finish} --workflow <name> [--job <name>] [--status ...]`, `summary generate --workflow ... --artifact-dir ...`, `report aggregate`, `artifacts collect`.

## CI System (`.github/workflows/ci.yaml`)

Unified monolithic pipeline, replaces the old 9-workflow split (which was moved to `.github/workflows/old/`: `1-master`, `build`, `lint`, `prep-build`, `publish`, `release`, `sec-scan`, `summarize`, `test`).

**Triggers:** all branch pushes, all PRs, tag pushes `v*`, `workflow_dispatch`.

**Jobs (in order):**
1. `initialization` — bootstraps `tools/ci`, computes version tags, sets `should_release` / `should_publish` outputs.
2. `build` — QEMU + buildx multi-arch build, saves tar artifact.
3. `mypy`, `ruff`, `ty`, `bandit` — run in parallel (`continue-on-error: true`, but each still fails its step on error detection). **`ty` is the CI-blocking type checker** — the job uses `ty check --output-format junit` and fails on `<failure>` elements or `failures="[1-9]"` in the XML output.
4. `test` — docker-compose-based test container run.
5. `release` — conditional on `BE-Master` / `BE-Staging` / tag push. Uploads `source-code.tar.gz` + `release-artifacts.tar.gz` + bandit + coverage.
6. `publish` — conditional on `BE-Master` / `BE-Staging`. Multi-arch image push to Docker Hub via `docker/build-push-action@v7` (`cache-from=gha`).
7. `final-summary` — always runs, aggregates everything.

**Branch → tag mapping:**
- `BE-Master` → `latest` + `be-prod` + short SHA + `ci-<sha>`.
- `BE-Staging` → `be-staging` + short SHA + `ci-<sha>`.
- `BE-Dev` → `be-dev` + short SHA + `ci-<sha>`.
- `master` → `latest` (legacy).

**Other workflows:**
- `build.yaml` — reusable build workflow (likely called by `ci.yaml`).
- `sync-docs.yaml` — documentation sync.

## Discord Integration (`app/discord.py`)

Webhook client with embed support. Classes: `Webhook`, `Embed`, `Footer`, `Image`, `Thumbnail`, `Author`, `Field`. Posts via `services.http_client` with `tenacity` retry (10 attempts, exponential backoff 4-10s).

```python
webhook = Webhook(url=DISCORD_AUDIT_LOG_WEBHOOK, username="Bot")
embed = Embed(title="Event", color=0xFF0000)
embed.add_field("User", username)
webhook.add_embed(embed)
await webhook.post()
```

## IP Resolution (`app/state/services.py`)

`IPResolver` instance on `app.state.services.ip_resolver` (initialized in lifespan).

Priority order for IP:
1. `CF-Connecting-IP` (Cloudflare).
2. First entry of `X-Forwarded-For`.
3. `X-Real-IP` (nginx).
4. `127.0.0.1` fallback.

Geolocation:
1. Cloudflare headers (`CF-IPCountry`, `CF-IPLatitude`, `CF-IPLongitude`).
2. Nginx geo headers (`X-Country-Code`, `X-Latitude`, `X-Longitude`).
3. Fallback: `ip-api.com` HTTP API via `httpx`.

Results cached in `IPResolver.cache: dict[str, IPAddress]`.

## OpenAPI Documentation

`BanchoAPI` subclass (in `init_api.py`) overrides `openapi()` to include host-mounted routes — FastAPI normally hides them because they're registered via `starlette.routing.Host`. Docs at `https://api.{domain}/docs`.

## Common Patterns

### Adding a new v1 endpoint (base)

1. Add handler to `app/api/v1/api.py`.
2. Decorate with `@router.get("/endpoint")` + `@error_catcher` (error_catcher re-raises, so FastAPI still returns the right status).
3. Auth check if needed: `if token is None or app.state.sessions.api_keys.get(token.credentials) is None: return ORJSONResponse({"status":"Invalid API key."}, status_code=401)`.
4. DB: `await app.state.services.database.fetch_one(...)`. Redis: `await app.state.services.redis.get(...)`.
5. Return `ORJSONResponse({...})`.

### Adding a new v1 hinaDir endpoint

1. Create or edit `app/api/v1/hinaDir/{module}.py`.
2. Define `router = APIRouter()` and routes.
3. Include the router in `app/api/v1/hinaDir/__init__.py`.

### Adding a new v2 endpoint

1. Add route to `app/api/v2/{module}.py`.
2. Define / reuse Pydantic models in `app/api/v2/models/{module}.py` (`str_strip_whitespace=True` is global).
3. Use `Success[T]` / `Failure` wrappers from `common/responses.py`.
4. Register new module router in `app/api/v2/__init__.py`.

### Adding a repository

1. Create `app/repositories/{name}.py`.
2. Define `Table(Base)` with SQLAlchemy column declarations.
3. Define `READ_PARAMS` tuple.
4. Define `TypedDict` row shape.
5. Implement async CRUD functions calling through `app.state.services.database`.

### Adding a migration

1. Append to `migrations/migrations.sql` under a new `# v{X.Y.Z}` header.
2. Bump the version in `pyproject.toml` to match (`make bump version=patch`).
3. Use `#` comments only — NEVER `--`.
4. End every statement with `;`.
5. MySQL DDL auto-commits; do not try to wrap in a transaction.

## Gotchas

| Issue | Cause / Fix |
|-------|-------------|
| API returns 405 | Missing `Host: api.{domain}` on the request (routing key) |
| API returns 401 | `users.api_key` not set for user ID 1; or `BOT_API_KEY` differs between kawaweb and kawata |
| `error_catcher` unexpected behavior | It now **re-raises** after logging — the old swallow-and-return-None behavior is gone |
| PP calc returns 0 | NaN/Inf result clamped to 0. Check the `.osu` file exists in `.data/osu/` |
| `--` in migration SQL | NEVER use `--` — the runner joins multi-line SQL into one line, causing `--` to swallow everything |
| Password mismatch | Must be `bcrypt(md5(plaintext))` not `bcrypt(plaintext)` |
| Beatmap cache stale | In-memory cache not invalidated. Use `/v1/update_map_status` not raw DB update |
| `fetch_all` / `execute` returns None | `MySQLError` was caught and logged. Check logs — the adapter silences DB errors |
| Redis leaderboard wrong | Key format must be `bancho:leaderboard:{mode}` — mode 0-3 vanilla, 4-6 relax, 8 autopilot |
| Debug logs not showing | Ensure `extra["filter"]["debugLevel"] ≤ settings.DEBUG_LEVEL` and `debugFocus` matches `DEBUG_FOCUS` or is unset |
| uvicorn hot-reload | Only enabled when `DEBUG_LEVEL >= 1` |
| Seasons endpoints error | `server_data.seasons_enabled` must be `'1'` AND v5.3.2 migration must have run (adds `stats.season_id` PK) |
| `akatsuki-pp-py` sync fails | `[tool.uv] no-build-package = ["akatsuki-pp-py"]` forbids source builds — wheel-only |
| Ty check fails locally but not in CI | `ty` excludes `.venv`, `tools`, `tests` via Makefile target; CI runs over everything with `--output-format junit` |
| Poetry commands break | Poetry is gone. Use UV (`uv sync`, `uv run`) — Poetry files may linger as historical cruft |
| mypy reports 200+ errors | The BE-Dev sync cleaned mypy + ty to zero. If you see regressions, look at the `0bc0bd4 Fix(Type-Checks)` commit for patterns |
| Cannot call bot API | Docker compose maps `BOT_API_KEY` → `API_KEY` for kawaweb; confirm both env vars match |
| Double-registered router | `api/__init__.py` and `init_api.py` both mount domain routers — the duplication is intentional for OpenAPI visibility (see `BanchoAPI.openapi`) |

## Related Reading

- `../CLAUDE.md` — kawataFullStack root (cross-service architecture, deploy, shared DB, inter-service auth).
- `../kawaweb/CLAUDE.md` — frontend (session/auth, templates, CSS, admin V2 UI).
- `plans/` — feature-specific design docs (logs overhaul, seasons, clans, cosmetics, donor, score hunts, sessions, api/migration).
- `AGENTS.md` — agent-oriented quick reference at repo root.
- `tools/ci/README.md` — CI orchestration tool full docs.
