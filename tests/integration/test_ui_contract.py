from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.ui import routes as ui_routes

client = TestClient(create_app())


def test_ui_page_returns_html_marker() -> None:
    response = client.get("/ui")
    assert response.status_code == 200
    # React build serves index.html with id="root" and bundled assets
    assert '<div id="root">' in response.text
    assert 'lang="vi"' in response.text


def test_ui_proxy_capabilities_contract() -> None:
    response = client.get("/ui/proxy/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert "assistant_name" in body
    assert "can_do" in body
    assert "quick_commands" in body
    assert "rule_targets" in body


def test_ui_proxy_dashboard_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes,
        "get_dashboard",
        lambda start_date=None, end_date=None, top_categories_limit=8: {
            "context": {"start_date": "2017-01-01", "end_date": "2017-12-31"},
            "overview": {"gmv": 1000.0, "total_orders": 10, "delivered_order_rate": 0.9, "avg_order_value": 100.0},
            "series": [{"month": "2017-01-01", "gmv": 100.0}],
            "series_row_count": 1,
            "top_categories": [{"category_name_en": "bed_bath_table", "total_orders": 9, "total_revenue": 500.0}],
            "warnings": [],
        },
    )

    response = client.post(
        "/ui/proxy/dashboard",
        json={"start_date": "2017-01-01", "end_date": "2017-12-31", "top_categories_limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overview"]["total_orders"] == 10
    assert body["series_row_count"] == 1
    assert isinstance(body["top_categories"], list)


def test_ui_proxy_chat_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes,
        "run_chat",
        lambda payload: {
            "mode": "agent",
            "assistant_message": "agent summary",
            "active_rules": {
                "allow_agent": True,
                "allow_kpi": True,
                "allow_sql": True,
                "allow_schema": True,
                "allow_definition": True,
                "sql_limit": 500,
            },
            "blocks": [
                {"type": "text", "title": None, "payload": {"text": "agent summary"}},
                {
                    "type": "table",
                    "title": "Agent Results",
                    "payload": {"columns": ["gmv"], "rows": [{"gmv": 1000.0}], "row_count": 1},
                },
            ],
            "trace": {
                "inferred_intent": "kpi_summary",
                "selected_tools": ["get_kpi_summary"],
                "sql": None,
                "confidence": 0.91,
                "warnings": [],
                "blocked": False,
            },
        },
    )

    response = client.post(
        "/ui/proxy/chat",
        json={"message": "show monthly revenue trend", "context": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "agent"
    assert body["assistant_message"] == "agent summary"
    assert body["trace"]["inferred_intent"] == "kpi_summary"
    assert body["blocks"][1]["type"] == "table"


def test_ui_proxy_query_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes,
        "run_query",
        lambda sql, limit=500: {
            "executed_sql": sql,
            "row_count": 1,
            "columns": ["x"],
            "rows": [{"x": 1}],
            "warnings": [],
        },
    )

    response = client.post(
        "/ui/proxy/query",
        json={"sql": "SELECT * FROM serving.kpi_overview", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert body["columns"] == ["x"]


def test_ui_proxy_query_unsafe_returns_400(monkeypatch) -> None:
    def _raise_unsafe(_sql: str, limit: int = 500):
        from app.db.sql_safety import UnsafeQueryError

        raise UnsafeQueryError("Only SELECT is allowed")

    monkeypatch.setattr(ui_routes, "run_query", _raise_unsafe)

    response = client.post(
        "/ui/proxy/query",
        json={"sql": "DELETE FROM x", "limit": 10},
    )
    assert response.status_code == 400
    assert "Only SELECT" in response.json()["detail"]
