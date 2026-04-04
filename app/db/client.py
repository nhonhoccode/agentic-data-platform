from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.db.sql_safety import enforce_limit, validate_read_only_sql


class DatabaseClient:
    """Thin Postgres client with read-only protections for analytics queries."""

    def __init__(self) -> None:
        self.settings = get_settings()

    @contextmanager
    def connect(self) -> Generator[psycopg.Connection, None, None]:
        conn = psycopg.connect(self.settings.postgres_dsn, row_factory=dict_row)
        try:
            yield conn
        finally:
            conn.close()

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
                cur.execute(f"SET statement_timeout = {self.settings.db_statement_timeout_ms}")
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
                cur.execute(f"SET statement_timeout = {self.settings.db_statement_timeout_ms}")
                cur.execute(sql_text, params)
                return cur.fetchall()
