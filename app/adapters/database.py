from __future__ import annotations

from typing import Any
from typing import cast
import json

from databases import Database as _Database
from databases.core import Transaction
from sqlalchemy.dialects.mysql.mysqldb import MySQLDialect_mysqldb
from sqlalchemy.sql.compiler import Compiled
from sqlalchemy.sql.expression import ClauseElement
from pymysql import MySQLError

from app import settings
from app.logging import log, Ansi
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
                f"Failed to execute SQL query: {e}", Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args)
                    }
                }, level=40
            )
            return None
        
        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {
                    "debugLevel": 2,
                    "debugFocus": "db"
                },
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            }, level=14
        )

        return dict(row._mapping) if row is not None else None

    async def fetch_all(
        self,
        query: MySQLQuery,
        params: MySQLParams = None,
    ) -> list[MySQLRow]:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)
        try:
            with Timer() as timer:
                rows = await self._database.fetch_all(query, params)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}", Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args)
                    }
                }, level=40
            )
            return None
        
        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {
                    "debugLevel": 2,
                    "debugFocus": "db"
                },
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            }, level=14
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
                f"Failed to execute SQL query: {e}", Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args)
                    }
                }, level=40
            )
            return None
        
        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {
                    "debugLevel": 2,
                    "debugFocus": "db"
                },
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            }, level=14
        )

        return val

    async def execute(self, query: MySQLQuery, params: MySQLParams = None) -> int:
        if isinstance(query, ClauseElement):
            query, params = self._compile(query)

        try:
            with Timer() as timer:
                rec_id = await self._database.execute(query, params)
        except MySQLError as e:
            log(
                f"Failed to execute SQL query: {e}", Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args)
                    }
                }, level=40
            )
            return None
        
        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {
                    "debugLevel": 2,
                    "debugFocus": "db"
                },
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            }, level=14
        )

        return cast(int, rec_id)

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
                f"Failed to execute SQL query: {e}", Ansi.RED,
                extra={
                    "query": query,
                    "params": params,
                    "error": {
                        "exception": str(e),
                        "type": str(type(e)),
                        "args": str(e.args)
                    }
                }, level=40
            )
            return None
        
        time_elapsed = timer.elapsed()
        log(
            f"Executed SQL query: {query} {params} in {time_elapsed * 1000:.2f} msec.",
            extra={
                "filter": {
                    "debugLevel": 2,
                    "debugFocus": "db"
                },
                "query": query,
                "params": params,
                "time_elapsed": time_elapsed,
            }, level=14
        )

    def transaction(
        self,
        *,
        force_rollback: bool = False,
        **kwargs: Any,
    ) -> Transaction:
        return self._database.transaction(force_rollback=force_rollback, **kwargs)