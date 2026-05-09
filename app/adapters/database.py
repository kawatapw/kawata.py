"""
Database Adapter - MySQL Database Connection and Query Management

This module provides a database adapter for MySQL connections in the osu!
server application. It implements the adapter pattern for database operations,
providing a clean abstraction layer between the application logic and the
underlying database driver, with comprehensive error handling, logging,
and performance monitoring.

The adapter wraps the databases library with MySQL-specific functionality,
including query compilation, parameter handling, transaction management,
and detailed logging of all database operations. It supports both raw SQL
queries and SQLAlchemy clause elements for flexible database interactions.

Key Features:
    - MySQL database connection management
    - Query compilation with SQLAlchemy integration
    - Comprehensive error handling and logging
    - Performance monitoring with execution timing
    - Transaction support with rollback capabilities
    - Support for both raw SQL and SQLAlchemy queries
    - Parameter binding and validation
    - Connection health checking

Integration Points:
    - Repository layer in app/repositories/
    - Application state in app/state/services.py
    - Settings configuration in app/settings.py
    - Logging system in app/logging.py
    - Timer utilities in app/timer.py

Database Operations:
    - fetch_one: Retrieve single row from query result
    - fetch_all: Retrieve all rows from query result
    - fetch_val: Retrieve single value from query result
    - execute: Execute INSERT/UPDATE/DELETE queries
    - execute_many: Execute batch operations
    - transaction: Manage database transactions
    - ping: Check database connection health

Query Types:
    - Raw SQL strings for direct database access
    - SQLAlchemy clause elements for type-safe queries
    - Parameterized queries for security
    - Batch operations for performance

Error Handling:
    - MySQLError catching and logging
    - Query and parameter logging for debugging
    - Execution time tracking for performance analysis
    - Graceful error recovery with None returns

Usage Pattern:
    # Create database connection
    db = Database("mysql://user:pass@host/db")
    await db.connect()

    # Fetch single row
    row = await db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})

    # Fetch all rows
    rows = await db.fetch_all("SELECT * FROM users WHERE active = 1")

    # Fetch single value
    count = await db.fetch_val("SELECT COUNT(*) FROM users")

    # Execute query
    await db.execute("INSERT INTO users (name) VALUES (:name)", {"name": "test"})

    # Use transaction
    async with db.transaction():
        await db.execute("UPDATE users SET balance = balance - 100 WHERE id = 1")
        await db.execute("UPDATE users SET balance = balance + 100 WHERE id = 2")

Related Files:
    - app/repositories/: Data access layer using this adapter
    - app/state/services.py: Database initialization
    - app/settings.py: Database configuration
    - app/logging.py: Logging utilities
"""

from __future__ import annotations

from typing import Any
from typing import cast

from databases import Database as _Database
from databases.core import Transaction
from pymysql import MySQLError
from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.sql.compiler import Compiled
from sqlalchemy.sql.expression import ClauseElement

from app.logging import Ansi
from app.logging import log
from app.timer import Timer


class MySQLDialect(MySQLDialect_mysqldb):
    default_paramstyle = "named"


DIALECT = MySQLDialect()

MySQLRow = dict[str, Any]
MySQLParams = dict[str, Any] | None
MySQLQuery = ClauseElement | str


class Database:
    def __init__(self, url: str) -> None:
        self._database = _Database(url)

    async def connect(self) -> None:
        await self._database.connect()

    async def disconnect(self) -> None:
        await self._database.disconnect()

    async def ping(self) -> bool:
        """Check if the database connection is alive."""
        try:
            # Execute a simple query that's lightweight and fast
            await self.fetch_val("SELECT 1")
            return True
        except Exception:
            return False

    def _compile(self, clause_element: ClauseElement) -> tuple[str, MySQLParams]:
        compiled: Compiled = clause_element.compile(
            dialect=DIALECT,
            compile_kwargs={"render_postcompile": True},
        )
        return str(compiled), compiled.params

    async def fetch_one(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
    ) -> MySQLRow | None:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        try:
            with Timer() as timer:
                row = await self._database.fetch_one(query, params)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}",
                Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args),
                    },
                },
                level=40,
            )
            return None

        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "db"},
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            },
            level=14,
        )

        return dict(row._mapping) if row is not None else None

    async def fetch_all(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
    ) -> list[MySQLRow] | None:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)
        try:
            with Timer() as timer:
                rows = await self._database.fetch_all(query, params)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}",
                Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args),
                    },
                },
                level=40,
            )
            return None

        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "db"},
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            },
            level=14,
        )

        return [dict(row._mapping) for row in rows]

    async def fetch_val(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
        column: Any = 0,
    ) -> Any:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        try:
            with Timer() as timer:
                val = await self._database.fetch_val(query, params, column)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}",
                Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args),
                    },
                },
                level=40,
            )
            return None

        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "db"},
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            },
            level=14,
        )

        return val

    async def execute(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
    ) -> int | None:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        try:
            with Timer() as timer:
                rec_id = await self._database.execute(query, params)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}",
                Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args),
                    },
                },
                level=40,
            )
            return None

        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "db"},
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            },
            level=14,
        )

        return cast("int", rec_id)

    # NOTE: this accepts str since current execute_many uses are not using alchemy.
    #       alchemy does execute_many in a single query so this method will be unneeded once raw SQL is not in use.
    async def execute_many(self, query: str, params: list[MySQLParams]) -> None:
        if isinstance(query, ClauseElement):
            query, _ = self._compile(query)

        try:
            with Timer() as timer:
                await self._database.execute_many(query, params)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}",
                Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args),
                    },
                },
                level=40,
            )
            return

        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {"debugLevel": 2, "debugFocus": "db"},
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            },
            level=14,
        )

    def transaction(
        self,
        *,
        force_rollback: bool = False,
        **kwargs: Any,
    ) -> Transaction:
        return self._database.transaction(force_rollback=force_rollback, **kwargs)
