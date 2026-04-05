from __future__ import annotations

from app.api.v2 import service as chat_service
from app.api.v2.schemas import ChatRequest, RuleConfig


def test_run_chat_help_mode() -> None:
    result = chat_service.run_chat(ChatRequest(message="/help"))
    assert result["mode"] == "help"
    assert "Commands" in result["assistant_message"]


def test_run_chat_rules_mode() -> None:
    result = chat_service.run_chat(ChatRequest(message="/rules"))
    assert result["mode"] == "rules"
    assert "Current runtime rules" in result["assistant_message"]


def test_run_chat_rule_sql_limit_usage() -> None:
    result = chat_service.run_chat(ChatRequest(message="/rule sql_limit"))
    assert result["mode"] == "rules_update"
    assert "Usage" in result["assistant_message"]


def test_run_chat_schema_missing_keyword() -> None:
    result = chat_service.run_chat(ChatRequest(message="/schema"))
    assert result["mode"] == "schema"
    assert "Usage" in result["assistant_message"]


def test_run_chat_schema_success(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "search_schema",
        lambda keyword, schemas=None: {
            "keyword": keyword,
            "match_count": 2,
            "matches": [
                {"table_schema": "serving", "table_name": "kpi_overview", "column_name": "gmv"},
                {"table_schema": "serving", "table_name": "kpi_monthly_sales", "column_name": "month"},
            ],
        },
    )
    result = chat_service.run_chat(ChatRequest(message="/schema gmv"))
    assert result["mode"] == "schema"
    assert any(block.type == "table" for block in result["blocks"])


def test_run_chat_definition_found(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "get_business_definition",
        lambda term: {
            "found": True,
            "definition": {"term": "GMV", "definition": "Gross merchandise value"},
        },
    )
    result = chat_service.run_chat(ChatRequest(message="/definition gmv"))
    assert result["mode"] == "definition"
    assert "GMV" in result["assistant_message"]


def test_run_chat_definition_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "get_business_definition",
        lambda term: {"found": False, "definition": None, "available_terms": ["gmv"]},
    )
    result = chat_service.run_chat(ChatRequest(message="/definition unknown"))
    assert result["mode"] == "definition"
    assert "not found" in result["assistant_message"].lower()


def test_run_chat_kpi_success(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "get_kpi_summary",
        lambda start_date=None, end_date=None: {
            "overview": {"total_orders": 10, "gmv": 1000.0, "delivered_order_rate": 0.9},
            "series": [
                {"month": "2017-01-01", "gmv": 100.0, "total_orders": 1},
                {"month": "2017-02-01", "gmv": 120.0, "total_orders": 2},
            ],
            "series_row_count": 2,
        },
    )
    result = chat_service.run_chat(ChatRequest(message="/kpi 2017-01-01 2017-12-31"))
    assert result["mode"] == "kpi"
    block_types = [block.type for block in result["blocks"]]
    assert "table" in block_types
    assert "figure" in block_types


def test_run_chat_kpi_blocked_by_rule() -> None:
    req = ChatRequest(message="/kpi", rules=RuleConfig(allow_kpi=False))
    result = chat_service.run_chat(req)
    assert result["mode"] == "kpi"
    assert result["trace"].blocked is True


def test_run_chat_inferred_help(monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "classify_intent", lambda question: "help_request")
    result = chat_service.run_chat(ChatRequest(message="show commands"))
    assert result["mode"] == "help"


def test_run_chat_agent_success_with_series(monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "classify_intent", lambda question: "kpi_summary")
    monkeypatch.setattr(
        chat_service,
        "run_workflow",
        lambda question, context=None: {
            "intent": "kpi_summary",
            "selected_tools": ["get_kpi_summary"],
            "sql": None,
            "result_summary": "Summary generated",
            "confidence": 0.91,
            "warnings": [],
            "raw_result": {
                "series": [
                    {"month": "2017-01", "gmv": 100.0},
                    {"month": "2017-02", "gmv": 150.0},
                ]
            },
        },
    )
    result = chat_service.run_chat(ChatRequest(message="show monthly revenue trend"))
    assert result["mode"] == "agent"
    assert any(block.type == "table" for block in result["blocks"])


def test_run_query_extracts_columns(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "query_data",
        lambda sql_text, limit=500: {
            "executed_sql": sql_text,
            "row_count": 2,
            "data": [{"gmv": 100.0, "month": "2017-01"}, {"gmv": 120.0, "month": "2017-02"}],
            "warnings": [],
        },
    )
    result = chat_service.run_query("SELECT * FROM serving.kpi_monthly_sales", 100)
    assert result["columns"] == ["gmv", "month"]
    assert result["row_count"] == 2


def test_get_dashboard_collects_top_category_warning(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "get_kpi_summary",
        lambda start_date=None, end_date=None: {"overview": {}, "series": [], "series_row_count": 0},
    )

    def _raise(_sql, _params=None):
        raise RuntimeError("table unavailable")

    monkeypatch.setattr(chat_service.service.db, "run_system_query", _raise)

    result = chat_service.get_dashboard(start_date=None, end_date=None, top_categories_limit=5)
    assert result["warnings"]
    assert "unavailable" in result["warnings"][0]
