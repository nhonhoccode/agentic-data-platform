from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings
from app.db.sql_safety import enforce_limit, validate_read_only_sql


@lru_cache(maxsize=1)
def _build_pool(conninfo: str, min_size: int, max_size: int) -> ConnectionPool:
    return ConnectionPool(
        conninfo=conninfo,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row},
        open=False,
    )


class DatabaseClient:
    """Thin Postgres client with read-only protections for analytics queries."""

    def __init__(self) -> None:
        self.settings = get_settings()
        dsn = (
            self.settings.postgres_readonly_dsn
            if self.settings.db_enforce_readonly_role
            else self.settings.postgres_dsn
        )
        self.pool = _build_pool(
            conninfo=dsn,
            min_size=self.settings.db_pool_min_size,
            max_size=self.settings.db_pool_max_size,
        )

    @contextmanager
    def connect(self) -> Generator[psycopg.Connection, None, None]:
        if self.pool.closed:
            self.pool.open(wait=True)
        with self.pool.connection() as conn:
            yield conn

    def run_read_query(
        self,
        sql_text: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
        limit_default: int = 500,
        limit_max: int = 5000,
    ) -> tuple[str, list[dict[str, Any]]]:
        validate_read_only_sql(sql_text)
        bounded_sql = enforce_limit(sql_text, default_limit=limit_default, max_limit=limit_max)

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = %s", (self.settings.db_statement_timeout_ms,))
                cur.execute(bounded_sql, params)
                rows = cur.fetchall()
                return bounded_sql, rows

    def run_system_query(
        self,
        sql_text: str,
        params: Sequence[Any] | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Used by trusted internal services for metadata and KPI lookups."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = %s", (self.settings.db_statement_timeout_ms,))
                cur.execute(sql_text, params)
                return cur.fetchall()
