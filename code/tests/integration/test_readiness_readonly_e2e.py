from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as app_main
from app.db import provision_readonly


class _ReadyDatabaseClient:
    def run_system_query(self, sql_text: str, params=None):
        assert "SELECT 1" in sql_text
        return [{"ok": 1}]


class _FailingDatabaseClient:
    def run_system_query(self, sql_text: str, params=None):
        raise RuntimeError("db unavailable")


class _FakeCursor:
    def __init__(self, store: list[str]):
        self.store = store

    def execute(self, query, params=None):
        self.store.append(f"{query} | params={params}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, store: list[str]):
        self.store = store

    def cursor(self):
        return _FakeCursor(self.store)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_readiness_endpoint_success(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "DatabaseClient", _ReadyDatabaseClient)

    with TestClient(app_main.create_app()) as client:
        response = client.get("/health/readiness")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_endpoint_failure(monkeypatch) -> None:
    monkeypatch.setattr(app_main, "DatabaseClient", _FailingDatabaseClient)

    with TestClient(app_main.create_app()) as client:
        response = client.get("/health/readiness")

    assert response.status_code == 503
    assert "Not ready" in response.json()["detail"]


def test_readonly_role_provisioning_generates_grants(monkeypatch) -> None:
    executed_sql: list[str] = []

    fake_settings = SimpleNamespace(
        db_enforce_readonly_role=True,
        postgres_readonly_user="olist_ro",
        postgres_readonly_password="secret",
        postgres_dsn="host=localhost",
        postgres_db="olist",
    )

    monkeypatch.setattr(provision_readonly, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(
        provision_readonly.psycopg,
        "connect",
        lambda *args, **kwargs: _FakeConnection(executed_sql),
    )

    provision_readonly.ensure_readonly_role()

    merged = "\n".join(executed_sql)
    assert "CREATE ROLE" in merged
    assert "GRANT CONNECT ON DATABASE" in merged
    assert "GRANT USAGE ON SCHEMA" in merged
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA" in merged
    assert "ALTER DEFAULT PRIVILEGES IN SCHEMA" in merged


def test_readonly_role_provisioning_skip_when_disabled(monkeypatch) -> None:
    fake_settings = SimpleNamespace(db_enforce_readonly_role=False)
    monkeypatch.setattr(provision_readonly, "get_settings", lambda: fake_settings)

    called = {"count": 0}

    def _connect(*args, **kwargs):
        called["count"] += 1
        return _FakeConnection([])

    monkeypatch.setattr(provision_readonly.psycopg, "connect", _connect)

    provision_readonly.ensure_readonly_role()
    assert called["count"] == 0
