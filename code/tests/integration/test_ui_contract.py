from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.ui import routes as ui_routes

client = TestClient(create_app())


def test_ui_page_returns_html_marker() -> None:
    response = client.get("/ui")
    assert response.status_code == 200
    assert "Olist Data Platform Demo UI" in response.text
    assert "olist-ui-root" in response.text


def test_ui_proxy_kpi_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes.service,
        "get_kpi_summary",
        lambda start_date=None, end_date=None: {
            "overview": {"gmv": 1000.0, "total_orders": 10},
            "series": [{"month": "2017-01-01", "gmv": 100.0}],
            "series_row_count": 1,
        },
    )

    response = client.post(
        "/ui/proxy/kpi",
        json={"start_date": "2017-01-01", "end_date": "2017-12-31"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "overview" in body
    assert body["series_row_count"] == 1


def test_ui_proxy_agent_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes,
        "run_workflow",
        lambda question, context=None: {
            "intent": "kpi_summary",
            "selected_tools": ["get_kpi_summary"],
            "sql": None,
            "result_summary": "ok",
            "confidence": 0.9,
            "warnings": [],
            "raw_result": {"overview": {"gmv": 1000.0}},
        },
    )

    response = client.post(
        "/ui/proxy/agent",
        json={"question": "show monthly revenue trend", "context": {}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "kpi_summary"


def test_ui_proxy_sql_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes.service,
        "query_data",
        lambda sql, limit=500: {
            "executed_sql": sql,
            "row_count": 1,
            "data": [{"x": 1}],
            "warnings": [],
        },
    )

    response = client.post(
        "/ui/proxy/sql",
        json={"sql": "SELECT 1", "limit": 10},
    )
    assert response.status_code == 200
    assert response.json()["row_count"] == 1


def test_ui_proxy_sql_unsafe_returns_400(monkeypatch) -> None:
    def _raise_unsafe(_sql: str, limit: int = 500):
        from app.db.sql_safety import UnsafeQueryError

        raise UnsafeQueryError("Only SELECT is allowed")

    monkeypatch.setattr(ui_routes.service, "query_data", _raise_unsafe)

    response = client.post(
        "/ui/proxy/sql",
        json={"sql": "DELETE FROM x", "limit": 10},
    )
    assert response.status_code == 400
    assert "Only SELECT" in response.json()["detail"]


def test_ui_proxy_schema_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes.service,
        "search_schema",
        lambda keyword, schemas=None: {
            "keyword": keyword,
            "match_count": 1,
            "matches": [{"table_schema": "serving", "table_name": "kpi_overview", "column_name": "gmv", "data_type": "numeric"}],
        },
    )

    response = client.post(
        "/ui/proxy/schema",
        json={"keyword": "gmv", "schemas": ["serving"]},
    )
    assert response.status_code == 200
    assert response.json()["match_count"] == 1


def test_ui_proxy_definition_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        ui_routes.service,
        "get_business_definition",
        lambda term: {
            "found": True,
            "definition": {"term": "Gross Merchandise Value", "definition": "Total paid order value."},
            "available_terms": None,
        },
    )

    response = client.get("/ui/proxy/definition", params={"term": "gmv"})
    assert response.status_code == 200
    assert response.json()["found"] is True
