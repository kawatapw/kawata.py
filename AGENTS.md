# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Build/Lint/Test Commands

- **Install dependencies**: `make install` (uses `uv sync --all-extras --dev`)
- **Run tests**: `make test` (runs via Docker containers - requires Docker)
- **Lint**: `make lint` (runs `uv run pre-commit run --all-files`)
- **Type check**: `make type-check` (runs `uv run mypy .`)
- **Single test**: `docker compose -f docker-compose.test.yml exec -T bancho-test pytest tests/path/to/test.py::test_name -v`
- **Run server**: `python main.py` or `uvicorn app.api.init_api:asgi_app --host 0.0.0.0 --port 8000`
- **Debug mode**: `DEBUG_LEVEL=1 python main.py` (enables auto-reload)

## Architecture

- **Layer pattern**: `app/repositories/` (data access) → `app/usecases/` (business logic) → `app/api/` (endpoints)
- **Objects** (`app/objects/`): Domain models (Player, Beatmap, Score, Match) - NOT Pydantic models
- **API v2 models** (`app/api/v2/models/`): Pydantic response models with custom `from_mapping()` classmethod for DB rows
- **State**: Global variables in `app/state/__init__.py` (event loop, packet handlers, shutdown flag)
- **Database adapter**: Custom `MySQLDialect` class in `app/adapters/database.py` wraps `databases` library
- **API domains**: Host-based routing - `c.{domain}` (CHO protocol), `osu.{domain}` (web API), `b.{domain}` (beatmaps), `api.{domain}` (developer API)

## Non-Obvious Patterns

- **isort auto-adds imports**: Configured to inject `from __future__ import annotations` into all files
- **Packet parsing**: Uses `memoryview` for zero-copy binary parsing in `app/packets.py`
- **Settings migration**: Use `support_deprecated_vars()` from `app/settings_utils.py` for env var changes
- **Logging colors**: Use `Ansi` enum from `app/logging.py` for colored console output
- **Test mocking**: External HTTP calls auto-mocked via `respx` fixture in `tests/conftest.py`
- **Background tasks**: Initialized in `app/bg_loops.py` via `asyncio.create_task()` during startup
- **Score submission**: Uses per-user async locks (`app/state/score_submission_locks`) for concurrency control
- **SQLAlchemy models**: Use old-style `mapper_registry` pattern in `app/repositories/__init__.py`, not modern `declarative_base()`
- **Pydantic config**: `str_strip_whitespace=True` is set globally for all v2 API models
- **Database queries**: Use `databases` library (async) with SQLAlchemy clause elements, not raw SQLAlchemy ORM
- **Packet handlers**: Registered via `@register` decorator in `app/api/domains/cho.py`, stored in `app.state.packets` dict
- **Encryption**: Score data encrypted with Rijndael CBC using version-specific keys in `app/encryption.py`
- **Geolocation**: Fetched from Cloudflare/Nginx headers or ip-api.com fallback in `app/state/services.py`
- **Housekeeping tasks**: Run in background - expired privilege removal (30min), ghost disconnection (100s), bot status update (5min)
- **Debug levels**: Custom log levels VERBOSE (11), DBGLV2 (14), DBGLV1 (16) in `app/logging.py`
- **Test environment**: Tests run in Docker with separate mysql-test and redis-test containers
- **Fixture scope**: `respx_mock` fixture auto-mocks all external HTTP calls; `configure_test_logging` is session-scoped
- **API response format**: v2 API uses `ORJSONResponse` for performance
- **BanchoAPI class**: Custom FastAPI subclass in `app/api/init_api.py` with modified OpenAPI schema generation
