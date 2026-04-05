from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.v2 import routes as v2_routes
from app.main import create_app

client = TestClient(create_app())
HEADERS = {"X-API-Key": "change-me"}


def test_v2_capabilities_contract() -> None:
    response = client.get("/api/v2/capabilities", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert "assistant_name" in body
    assert "quick_commands" in body
    assert "rule_targets" in body


def test_v2_chat_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        v2_routes,
        "run_chat",
        lambda payload: {
            "mode": "agent",
            "assistant_message": "Summary generated",
            "active_rules": {
                "allow_agent": True,
                "allow_kpi": True,
                "allow_sql": True,
                "allow_schema": True,
                "allow_definition": True,
                "sql_limit": 500,
            },
            "blocks": [{"type": "text", "title": None, "payload": {"text": "Summary generated"}}],
            "trace": {
                "inferred_intent": "kpi_summary",
                "selected_tools": ["get_kpi_summary"],
                "sql": None,
                "confidence": 0.9,
                "warnings": [],
                "blocked": False,
            },
        },
    )

    response = client.post(
        "/api/v2/chat",
        headers=HEADERS,
        json={"message": "show monthly revenue trend", "context": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "agent"
    assert body["trace"]["inferred_intent"] == "kpi_summary"


def test_v2_query_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        v2_routes,
        "run_query",
        lambda sql, limit=500: {
            "executed_sql": sql,
            "row_count": 1,
            "columns": ["gmv"],
            "rows": [{"gmv": 100.0}],
            "warnings": [],
        },
    )

    response = client.post(
        "/api/v2/query",
        headers=HEADERS,
        json={"sql": "SELECT * FROM serving.kpi_overview", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert body["columns"] == ["gmv"]


def test_v2_query_unsafe_returns_400(monkeypatch) -> None:
    def _raise_unsafe(_sql: str, limit: int = 500):
        from app.db.sql_safety import UnsafeQueryError

        raise UnsafeQueryError("Blocked keyword")

    monkeypatch.setattr(v2_routes, "run_query", _raise_unsafe)

    response = client.post(
        "/api/v2/query",
        headers=HEADERS,
        json={"sql": "DELETE FROM x", "limit": 10},
    )
    assert response.status_code == 400
    assert "Blocked keyword" in response.json()["detail"]
