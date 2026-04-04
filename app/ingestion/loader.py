from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg import sql

from app.config import get_settings
from app.ingestion.schema import DATASET_SPECS, DatasetSpec

CHUNK_SIZE = 1024 * 1024


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

    with psycopg.connect(settings.postgres_dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS raw")

        for spec in DATASET_SPECS:
            csv_path = data_dir / spec.file_name
            if not csv_path.exists():
                raise FileNotFoundError(f"Expected dataset file not found: {csv_path}")

            print(f"[INGEST] Loading {spec.file_name} -> raw.{spec.table_name}")
            with conn.cursor() as cursor:
                _create_raw_table(cursor, spec)
                _copy_csv_to_table(conn, cursor, spec, csv_path)
            conn.commit()

    print("[INGEST] Completed loading full Olist dataset into raw schema.")


def main() -> None:
    ingest_all()


if __name__ == "__main__":
    main()
