# Code Mode Rules (Non-Obvious Only)

## Import Conventions
- `from __future__ import annotations` is auto-injected by isort - do NOT add manually
- Use `# isort: dont-add-imports` comment in `__init__.py` files to prevent auto-imports
- Import order: stdlib → third-party → local (enforced by ruff)

## Database Patterns
- Use `databases` library (async) with SQLAlchemy clause elements, NOT raw SQLAlchemy ORM
- Repository functions return TypedDict or raw dicts, NOT ORM objects
- Use `MySQLDialect` from `app/adapters/database.py` for query compilation
- Database models use old-style `mapper_registry` pattern, not modern `declarative_base()`

## API Response Models
- All v2 API models inherit from `BaseModel` in `app/api/v2/models/__init__.py`
- Use `from_mapping()` classmethod to create models from database rows
- `str_strip_whitespace=True` is set globally - strings auto-trimmed
- Use `ORJSONResponse` for v2 API responses (faster than default JSON)

## Packet Handling
- Packet handlers registered via `@register` decorator in `app/api/domains/cho.py`
- Handlers stored in `app.state.packets` dict with keys "all" or "restricted"
- Use `memoryview` for zero-copy binary parsing in packet operations
- Packet IDs are `IntEnum` values from `ClientPackets` and `ServerPackets`

## Object System
- Domain objects in `app/objects/` are NOT Pydantic models - they're plain Python classes
- Player class manages session state, privileges, social features, and packet queue
- Use `player.enqueue()` to send packets to client
- Score submission uses per-user async locks from `app/state/score_submission_locks`

## Settings & Configuration
- Use `support_deprecated_vars()` from `app/settings_utils.py` for env var migrations
- Settings loaded from `.env` file via `python-dotenv`
- Database DSN constructed in `app/settings.py` from individual env vars

## Logging
- Use `log()` function from `app/logging.py` with `Ansi` enum for colors
- Custom log levels: VERBOSE (11), DBGLV2 (14), DBGLV1 (16)
- Debug filtering via `filter` parameter with `debugLevel` and `debugFocus` keys

## Error Handling
- Use `@error_catcher` decorator from `app/logging.py` for exception handling
- Database errors caught as `MySQLError` from pymysql
- HTTP client errors handled via httpx exception types
