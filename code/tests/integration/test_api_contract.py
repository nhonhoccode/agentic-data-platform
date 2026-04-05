from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.main import create_app

client = TestClient(create_app())
HEADERS = {"X-API-Key": "change-me"}


def test_health_endpoint_requires_and_accepts_api_key() -> None:
    response = client.get("/health", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_liveness_endpoint_is_public() -> None:
    response = client.get("/health/liveness")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_query_data_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        routes.service,
        "query_data",
        lambda sql, limit=500: {
            "executed_sql": sql,
            "row_count": 1,
            "data": [{"gmv": 100.0}],
            "warnings": [],
        },
    )

    response = client.post(
        "/api/v1/query_data",
        headers=HEADERS,
        json={"sql": "SELECT 1", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 1
    assert "data" in body
    assert response.headers["Deprecation"] == "true"


def test_search_schema_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        routes.service,
        "search_schema",
        lambda keyword, schemas=None: {
            "keyword": keyword,
            "match_count": 1,
            "matches": [{"table_schema": "serving", "table_name": "kpi_overview", "column_name": "gmv", "data_type": "numeric"}],
        },
    )

    response = client.post(
        "/api/v1/search_schema",
        headers=HEADERS,
        json={"keyword": "gmv", "schemas": ["serving"]},
    )
    assert response.status_code == 200
    assert response.json()["match_count"] == 1


def test_business_definition_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        routes.service,
        "get_business_definition",
        lambda term: {
            "found": True,
            "definition": {"term": "Gross Merchandise Value", "definition": "Total paid order value."},
            "available_terms": None,
        },
    )

    response = client.get(
        "/api/v1/get_business_definition",
        headers=HEADERS,
        params={"term": "gmv"},
    )
    assert response.status_code == 200
    assert response.json()["found"] is True


def test_get_kpi_summary_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        routes.service,
        "get_kpi_summary",
        lambda start_date=None, end_date=None: {
            "overview": {"gmv": 1000.0},
            "series": [{"month": "2017-01-01", "gmv": 100.0}],
            "series_row_count": 1,
        },
    )

    response = client.post(
        "/api/v1/get_kpi_summary",
        headers=HEADERS,
        json={"start_date": "2017-01-01", "end_date": "2017-12-31"},
    )
    assert response.status_code == 200
    assert response.json()["series_row_count"] == 1


def test_run_agent_workflow_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "run_workflow",
        lambda question, context=None: {
            "intent": "kpi_summary",
            "selected_tools": ["get_kpi_summary"],
            "sql": None,
            "result_summary": "Summary generated",
            "confidence": 0.9,
            "warnings": [],
            "raw_result": {"overview": {"gmv": 1000.0}},
        },
    )

    response = client.post(
        "/api/v1/run_agent_workflow",
        headers=HEADERS,
        json={"question": "show monthly revenue trend", "context": {}},
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "kpi_summary"
