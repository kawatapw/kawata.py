# Ask Mode Rules (Non-Obvious Only)

## Project Structure
- `app/objects/` contains domain models (Player, Beatmap, Score, Match) - NOT Pydantic models
- `app/repositories/` uses old-style `mapper_registry` pattern, not modern `declarative_base()`
- `app/api/v2/models/` are Pydantic response models with custom `from_mapping()` classmethod
- `app/state/` contains global variables (event loop, packet handlers, shutdown flag)

## API Organization
- Host-based routing: `c.{domain}` (CHO protocol), `osu.{domain}` (web API), `b.{domain}` (beatmaps), `api.{domain}` (developer API)
- v2 API uses `ORJSONResponse` for performance
- Packet handlers registered via `@register` decorator in `app/api/domains/cho.py`
- BanchoAPI class in `app/api/init_api.py` extends FastAPI with custom OpenAPI schema generation

## Database Layer
- Uses `databases` library (async) with SQLAlchemy clause elements, NOT raw SQLAlchemy ORM
- Repository functions return TypedDict or raw dicts, NOT ORM objects
- Custom `MySQLDialect` class in `app/adapters/database.py` wraps `databases` library
- Database DSN constructed in `app/settings.py` from individual env vars

## Configuration
- Settings loaded from `.env` file via `python-dotenv`
- Use `support_deprecated_vars()` from `app/settings_utils.py` for env var migrations
- Debug levels: VERBOSE (11), DBGLV2 (14), DBGLV1 (16) in `app/logging.py`
- Log configuration loaded from `logging.yaml` file

## Testing
- Tests run in Docker with separate mysql-test and redis-test containers
- Test database initialized via `scripts/run-tests.sh`
- External HTTP calls auto-mocked via `respx` fixture in `tests/conftest.py`
- `configure_test_logging` fixture is session-scoped

## Background Tasks
- Housekeeping tasks in `app/bg_loops.py`:
  - Expired privilege removal: every 30 minutes
  - Ghost disconnection: every 100 seconds
  - Bot status update: every 5 minutes
  - Debug level watch: every 1 second
- Tasks initialized via `asyncio.create_task()` during startup

## Packet System
- Uses `memoryview` for zero-copy binary parsing in `app/packets.py`
- Packet IDs are `IntEnum` values from `ClientPackets` and `ServerPackets`
- Handlers stored in `app.state.packets` dict with keys "all" or "restricted"
- Score submission uses per-user async locks from `app/state/score_submission_locks`
