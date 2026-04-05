from __future__ import annotations

from types import SimpleNamespace

from app.db import client as db_client_module


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, rows):
        self.cursor_obj = _FakeCursor(rows)

    def cursor(self):
        return self.cursor_obj


class _PoolConnectionCtx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn, closed=True):
        self.conn = conn
        self.closed = closed
        self.open_calls: list[bool] = []

    def open(self, wait=True):
        self.open_calls.append(wait)
        self.closed = False

    def connection(self):
        return _PoolConnectionCtx(self.conn)


def _make_settings(enforce_readonly: bool) -> SimpleNamespace:
    return SimpleNamespace(
        postgres_dsn="postgres admin dsn",
        postgres_readonly_dsn="postgres readonly dsn",
        db_enforce_readonly_role=enforce_readonly,
        db_pool_min_size=1,
        db_pool_max_size=8,
        db_statement_timeout_ms=120000,
    )


def test_database_client_uses_readonly_dsn_when_enabled(monkeypatch) -> None:
    captured = {}

    def _fake_build_pool(conninfo, min_size, max_size):
        captured["conninfo"] = conninfo
        return _FakePool(_FakeConnection([]), closed=False)

    monkeypatch.setattr(db_client_module, "_build_pool", _fake_build_pool)
    monkeypatch.setattr(db_client_module, "get_settings", lambda: _make_settings(True))

    db_client_module.DatabaseClient()
    assert captured["conninfo"] == "postgres readonly dsn"


def test_database_client_uses_admin_dsn_when_readonly_disabled(monkeypatch) -> None:
    captured = {}

    def _fake_build_pool(conninfo, min_size, max_size):
        captured["conninfo"] = conninfo
        return _FakePool(_FakeConnection([]), closed=False)

    monkeypatch.setattr(db_client_module, "_build_pool", _fake_build_pool)
    monkeypatch.setattr(db_client_module, "get_settings", lambda: _make_settings(False))

    db_client_module.DatabaseClient()
    assert captured["conninfo"] == "postgres admin dsn"


def test_run_read_query_validates_and_bounds(monkeypatch) -> None:
    fake_conn = _FakeConnection([{"x": 1}])
    fake_pool = _FakePool(fake_conn, closed=True)

    monkeypatch.setattr(db_client_module, "_build_pool", lambda *args, **kwargs: fake_pool)
    monkeypatch.setattr(db_client_module, "get_settings", lambda: _make_settings(True))

    validate_calls = {"sql": None}
    monkeypatch.setattr(
        db_client_module,
        "validate_read_only_sql",
        lambda sql_text: validate_calls.update({"sql": sql_text}),
    )
    monkeypatch.setattr(
        db_client_module,
        "enforce_limit",
        lambda sql_text, default_limit=500, max_limit=5000: "SELECT 1 LIMIT 5",
    )

    client = db_client_module.DatabaseClient()
    executed_sql, rows = client.run_read_query("SELECT 1")

    assert validate_calls["sql"] == "SELECT 1"
    assert executed_sql == "SELECT 1 LIMIT 5"
    assert rows == [{"x": 1}]
    assert fake_pool.open_calls == [True]

    executed = fake_conn.cursor_obj.executed
    assert executed[0][0] == "SET statement_timeout = %s"
    assert executed[1][0] == "SELECT 1 LIMIT 5"


def test_run_system_query_executes_with_timeout(monkeypatch) -> None:
    fake_conn = _FakeConnection([{"ok": 1}])
    fake_pool = _FakePool(fake_conn, closed=False)

    monkeypatch.setattr(db_client_module, "_build_pool", lambda *args, **kwargs: fake_pool)
    monkeypatch.setattr(db_client_module, "get_settings", lambda: _make_settings(True))

    client = db_client_module.DatabaseClient()
    rows = client.run_system_query("SELECT 1", params={"a": 1})

    assert rows == [{"ok": 1}]
    executed = fake_conn.cursor_obj.executed
    assert executed[0][0] == "SET statement_timeout = %s"
    assert executed[1][0] == "SELECT 1"
    assert executed[1][1] == {"a": 1}
