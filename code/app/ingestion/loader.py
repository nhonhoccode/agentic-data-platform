from __future__ import annotations

import time
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

from app.config import get_settings
from app.ingestion.schema import DATASET_SPECS, DatasetSpec

CHUNK_SIZE = 1024 * 1024


def _ensure_ingestion_metadata(cursor: psycopg.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.ingestion_runs (
            run_id UUID PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMPTZ,
            status TEXT NOT NULL,
            duration_seconds NUMERIC(12, 2),
            error_message TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS raw.ingestion_run_tables (
            run_id UUID NOT NULL REFERENCES raw.ingestion_runs(run_id) ON DELETE CASCADE,
            table_name TEXT NOT NULL,
            row_count BIGINT NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (run_id, table_name)
        )
        """
    )


def _create_raw_table(cursor: psycopg.Cursor, spec: DatasetSpec) -> None:
    column_definitions = sql.SQL(", ").join(
        sql.SQL("{} TEXT").format(sql.Identifier(column)) for column in spec.columns
    )
    cursor.execute(
        sql.SQL("DROP TABLE IF EXISTS raw.{} CASCADE").format(sql.Identifier(spec.table_name))
    )
    cursor.execute(
        sql.SQL("CREATE TABLE raw.{} ({})").format(
            sql.Identifier(spec.table_name),
            column_definitions,
        )
    )


def _copy_csv_to_table(conn: psycopg.Connection, cursor: psycopg.Cursor, spec: DatasetSpec, csv_path: Path) -> None:
    copy_sql = sql.SQL("COPY raw.{} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
        sql.Identifier(spec.table_name),
        sql.SQL(", ").join(sql.Identifier(column) for column in spec.columns),
    )

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        with cursor.copy(copy_sql.as_string(conn)) as copy:
            while True:
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                copy.write(chunk)


def ingest_all() -> None:
    settings = get_settings()
    data_dir = settings.resolved_data_dir
    run_id = uuid.uuid4()
    started_at = time.monotonic()

    with psycopg.connect(settings.postgres_dsn) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")
                _ensure_ingestion_metadata(cursor)
                cursor.execute(
                    "INSERT INTO raw.ingestion_runs (run_id, status) VALUES (%s, %s)",
                    (run_id, "running"),
                )
            conn.commit()

            for spec in DATASET_SPECS:
                csv_path = data_dir / spec.file_name
                if not csv_path.exists():
                    raise FileNotFoundError(f"Expected dataset file not found: {csv_path}")

                print(f"[INGEST] Loading {spec.file_name} -> raw.{spec.table_name}")
                with conn.cursor() as cursor:
                    _create_raw_table(cursor, spec)
                    _copy_csv_to_table(conn, cursor, spec, csv_path)
                    cursor.execute(
                        sql.SQL("SELECT COUNT(*)::bigint AS row_count FROM raw.{}").format(
                            sql.Identifier(spec.table_name)
                        )
                    )
                    row_count = int(cursor.fetchone()[0])
                    cursor.execute(
                        """
                        INSERT INTO raw.ingestion_run_tables (run_id, table_name, row_count)
                        VALUES (%s, %s, %s)
                        """,
                        (run_id, spec.table_name, row_count),
                    )
                conn.commit()

            duration = round(time.monotonic() - started_at, 2)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE raw.ingestion_runs
                    SET status = %s, finished_at = NOW(), duration_seconds = %s
                    WHERE run_id = %s
                    """,
                    ("success", duration, run_id),
                )
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            duration = round(time.monotonic() - started_at, 2)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE raw.ingestion_runs
                    SET status = %s, finished_at = NOW(), duration_seconds = %s, error_message = %s
                    WHERE run_id = %s
                    """,
                    ("failed", duration, str(exc)[:2000], run_id),
                )
            conn.commit()
            raise

    print(f"[INGEST] Completed loading full Olist dataset into raw schema. run_id={run_id}")


def main() -> None:
    ingest_all()


if __name__ == "__main__":
    main()
