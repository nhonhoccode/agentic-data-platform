from __future__ import annotations

from app.api.v2 import service as chat_service
from app.api.v2.schemas import ChatRequest


def test_run_chat_sql_returns_table_and_figure(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.service,
        "query_data",
        lambda sql, limit=500: {
            "executed_sql": sql,
            "row_count": 3,
            "data": [
                {"month": "2017-01", "gmv": 100.0},
                {"month": "2017-02", "gmv": 120.0},
                {"month": "2017-03", "gmv": 140.0},
            ],
            "warnings": [],
        },
    )

    result = chat_service.run_chat(ChatRequest(message="/sql SELECT month, gmv FROM serving.kpi_monthly_sales"))

    assert result["mode"] == "sql"
    block_types = [block.type for block in result["blocks"]]
    assert "table" in block_types
    assert "figure" in block_types


def test_run_chat_rule_update() -> None:
    result = chat_service.run_chat(ChatRequest(message="/rule sql off"))
    assert result["mode"] == "rules_update"
    assert result["active_rules"].allow_sql is False


def test_run_chat_blocked_by_rule(monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "classify_intent", lambda question: "sql_query")

    request = ChatRequest(
        message="show monthly revenue trend",
        rules={
            "allow_agent": True,
            "allow_kpi": True,
            "allow_sql": False,
            "allow_schema": True,
            "allow_definition": True,
            "sql_limit": 500,
        },
    )

    result = chat_service.run_chat(request)
    assert result["trace"].blocked is True
    assert "allow_sql=off" in result["assistant_message"]
