# Architect Mode Rules (Non-Obvious Only)

## Layer Architecture
- **Repository Layer** (`app/repositories/`): Data access using `databases` library (async) with SQLAlchemy clause elements
- **Use Case Layer** (`app/usecases/`): Business logic abstraction between API and repositories
- **API Layer** (`app/api/`): FastAPI endpoints with host-based routing
- **Object Layer** (`app/objects/`): Domain models (Player, Beatmap, Score, Match) - NOT Pydantic models

## Database Architecture
- Custom `MySQLDialect` class in `app/adapters/database.py` wraps `databases` library
- Old-style `mapper_registry` pattern in `app/repositories/__init__.py`, not modern `declarative_base()`
- Repository functions return TypedDict or raw dicts, NOT ORM objects
- Database DSN constructed in `app/settings.py` from individual env vars

## API Architecture
- Host-based routing: `c.{domain}` (CHO protocol), `osu.{domain}` (web API), `b.{domain}` (beatmaps), `api.{domain}` (developer API)
- v2 API uses `ORJSONResponse` for performance
- Pydantic models in `app/api/v2/models/` with custom `from_mapping()` classmethod
- `str_strip_whitespace=True` set globally for all v2 API models
- BanchoAPI class in `app/api/init_api.py` extends FastAPI with custom OpenAPI schema generation

## State Management
- Global variables in `app/state/__init__.py` (event loop, packet handlers, shutdown flag)
- Score submission uses per-user async locks from `app/state/score_submission_locks`
- Player sessions tracked in `app/state/sessions.py`
- Packet handlers stored in `app.state.packets` dict with keys "all" or "restricted"

## Packet System Architecture
- Uses `memoryview` for zero-copy binary parsing in `app/packets.py`
- Packet IDs are `IntEnum` values from `ClientPackets` and `ServerPackets`
- Handlers registered via `@register` decorator in `app/api/domains/cho.py`
- Score data encrypted with Rijndael CBC using version-specific keys in `app/encryption.py`

## Background Task Architecture
- Housekeeping tasks in `app/bg_loops.py`:
  - Expired privilege removal: every 30 minutes
  - Ghost disconnection: every 100 seconds
  - Bot status update: every 5 minutes
  - Debug level watch: every 1 second
- Tasks initialized via `asyncio.create_task()` during startup

## Testing Architecture
- Tests run in Docker with separate mysql-test and redis-test containers
- Test database initialized via `scripts/run-tests.sh`
- External HTTP calls auto-mocked via `respx` fixture in `tests/conftest.py`
- `configure_test_logging` fixture is session-scoped

## Configuration Architecture
- Settings loaded from `.env` file via `python-dotenv`
- Use `support_deprecated_vars()` from `app/settings_utils.py` for env var migrations
- Debug levels: VERBOSE (11), DBGLV2 (14), DBGLV1 (16) in `app/logging.py`
- Log configuration loaded from `logging.yaml` file
