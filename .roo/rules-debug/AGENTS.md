# Debug Mode Rules (Non-Obvious Only)

## Debug Levels
- Custom log levels: VERBOSE (11), DBGLV2 (14), DBGLV1 (16) in `app/logging.py`
- Enable debug mode: `DEBUG_LEVEL=1 python main.py` (enables auto-reload)
- Debug filtering via `filter` parameter with `debugLevel` and `debugFocus` keys
- Debug level watcher runs in background via `DebugLevelWatcher.watch()` in `app/bg_loops.py`

## Logging System
- Use `log()` function from `app/logging.py` with `Ansi` enum for colors
- Structured logging via structlog with JSON output support
- Log configuration loaded from `logging.yaml` file
- Request logging includes IP resolution and geolocation data

## Database Debugging
- Database queries logged with execution time in `app/adapters/database.py`
- MySQL errors caught as `MySQLError` from pymysql
- Connection health check via `ping()` method
- Transaction support with rollback capabilities

## HTTP Client Debugging
- External HTTP calls auto-mocked in tests via `respx` fixture in `tests/conftest.py`
- HTTP client errors handled via httpx exception types
- Geolocation fallback to ip-api.com if Cloudflare/Nginx headers missing

## State Debugging
- Global state in `app/state/__init__.py` includes event loop, packet handlers, shutdown flag
- Score submission locks per-user in `app/state/score_submission_locks`
- Player sessions tracked in `app/state/sessions.py`
- Packet handlers stored in `app.state.packets` dict with keys "all" or "restricted"

## Background Task Debugging
- Housekeeping tasks in `app/bg_loops.py`:
  - Expired privilege removal: every 30 minutes
  - Ghost disconnection: every 100 seconds
  - Bot status update: every 5 minutes
  - Debug level watch: every 1 second
- Tasks initialized via `asyncio.create_task()` during startup

## Test Debugging
- Tests run in Docker with separate mysql-test and redis-test containers
- Test database initialized via `scripts/run-tests.sh`
- `configure_test_logging` fixture is session-scoped
- `respx_mock` fixture auto-mocks all external HTTP calls
