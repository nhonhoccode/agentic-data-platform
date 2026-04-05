from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ingestion import loader
from app.ingestion.schema import DatasetSpec


class _DummyComposable:
    def __init__(self, text: str):
        self.text = text

    def format(self, *args):
        rendered = self.text
        for arg in args:
            rendered = rendered.replace("{}", str(arg), 1)
        return _DummyComposable(rendered)

    def join(self, values):
        return _DummyComposable(self.text.join(str(value) for value in values))

    def as_string(self, _conn):
        return self.text

    def __str__(self):
        return self.text


def _patch_dummy_sql(monkeypatch):
    dummy_sql = SimpleNamespace(
        SQL=lambda text: _DummyComposable(text),
        Identifier=lambda text: _DummyComposable(text),
    )
    monkeypatch.setattr(loader, "sql", dummy_sql)


class _FakeCopy:
    def __init__(self):
        self.writes: list[str] = []

    def write(self, chunk: str):
        self.writes.append(chunk)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.fetchone_value = (0,)

    def execute(self, query, params=None):
        sql_text = query.as_string(self.conn) if hasattr(query, "as_string") else str(query)
        self.conn.executed.append((sql_text, params))
        if "SELECT COUNT(*)" in sql_text:
            self.fetchone_value = (7,)

    def fetchone(self):
        return self.fetchone_value

    def copy(self, _sql_text):
        copy_obj = _FakeCopy()
        self.conn.copy_objects.append(copy_obj)
        return copy_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self):
        self.executed: list[tuple[str, object]] = []
        self.commit_count = 0
        self.copy_objects: list[_FakeCopy] = []

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commit_count += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ensure_ingestion_metadata_creates_tables() -> None:
    conn = _FakeConnection()
    cursor = _FakeCursor(conn)

    loader._ensure_ingestion_metadata(cursor)

    merged = "\n".join(sql for sql, _ in conn.executed)
    assert "CREATE TABLE IF NOT EXISTS raw.ingestion_runs" in merged
    assert "CREATE TABLE IF NOT EXISTS raw.ingestion_run_tables" in merged


def test_create_raw_table_runs_drop_and_create(monkeypatch) -> None:
    _patch_dummy_sql(monkeypatch)
    conn = _FakeConnection()
    cursor = _FakeCursor(conn)

    spec = DatasetSpec(file_name="x.csv", table_name="orders", columns=["order_id", "customer_id"])
    loader._create_raw_table(cursor, spec)

    merged = "\n".join(sql for sql, _ in conn.executed)
    assert "DROP TABLE IF EXISTS raw.orders CASCADE" in merged
    assert "CREATE TABLE raw.orders" in merged


def test_copy_csv_to_table_streams_data(monkeypatch, tmp_path: Path) -> None:
    _patch_dummy_sql(monkeypatch)

    spec = DatasetSpec(file_name="mini.csv", table_name="orders", columns=["order_id", "customer_id"])
    csv_path = tmp_path / spec.file_name
    csv_path.write_text("order_id,customer_id\nord-1,cus-1\n", encoding="utf-8")

    conn = _FakeConnection()
    cursor = _FakeCursor(conn)

    loader._copy_csv_to_table(conn, cursor, spec, csv_path)

    assert conn.copy_objects
    written = "".join(conn.copy_objects[0].writes)
    assert "order_id,customer_id" in written
    assert "ord-1,cus-1" in written


def test_ingest_all_success_records_run(monkeypatch, tmp_path: Path) -> None:
    _patch_dummy_sql(monkeypatch)

    spec = DatasetSpec(file_name="orders.csv", table_name="orders", columns=["order_id"])
    (tmp_path / spec.file_name).write_text("order_id\nord-1\n", encoding="utf-8")

    fake_settings = SimpleNamespace(resolved_data_dir=tmp_path, postgres_dsn="host=localhost")
    fake_conn = _FakeConnection()

    monkeypatch.setattr(loader, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(loader, "DATASET_SPECS", [spec])
    monkeypatch.setattr(loader.psycopg, "connect", lambda _dsn: fake_conn)
    monkeypatch.setattr(loader, "_copy_csv_to_table", lambda *args, **kwargs: None)

    loader.ingest_all()

    sql_log = "\n".join(sql for sql, _ in fake_conn.executed)
    assert "INSERT INTO raw.ingestion_runs" in sql_log
    assert "INSERT INTO raw.ingestion_run_tables" in sql_log
    assert "SET status = %s, finished_at = NOW(), duration_seconds = %s" in sql_log
    assert fake_conn.commit_count >= 3


def test_ingest_all_failure_updates_failed_status(monkeypatch, tmp_path: Path) -> None:
    _patch_dummy_sql(monkeypatch)

    spec = DatasetSpec(file_name="missing.csv", table_name="orders", columns=["order_id"])
    fake_settings = SimpleNamespace(resolved_data_dir=tmp_path, postgres_dsn="host=localhost")
    fake_conn = _FakeConnection()

    monkeypatch.setattr(loader, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(loader, "DATASET_SPECS", [spec])
    monkeypatch.setattr(loader.psycopg, "connect", lambda _dsn: fake_conn)

    with pytest.raises(FileNotFoundError):
        loader.ingest_all()

    failed_updates = [params for sql, params in fake_conn.executed if "SET status = %s" in sql]
    assert failed_updates
    assert failed_updates[-1][0] == "failed"
