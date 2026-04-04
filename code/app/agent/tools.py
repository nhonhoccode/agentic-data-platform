from __future__ import annotations

import re
from typing import Any

from app.definitions.business_glossary import BUSINESS_DEFINITIONS
from app.services.query_service import QueryService

service = QueryService()


def search_schema_tool(keyword: str, schemas: list[str] | None = None) -> dict[str, Any]:
    return service.search_schema(keyword, schemas=schemas)


def business_definition_tool(term: str) -> dict[str, Any]:
    return service.get_business_definition(term)


def kpi_summary_tool(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    from datetime import date

    parsed_start = date.fromisoformat(start_date) if start_date else None
    parsed_end = date.fromisoformat(end_date) if end_date else None
    return service.get_kpi_summary(start_date=parsed_start, end_date=parsed_end)


STOPWORDS = {
    "show",
    "list",
    "find",
    "what",
    "is",
    "the",
    "schema",
    "table",
    "column",
    "for",
    "of",
    "me",
    "please",
    "definition",
    "meaning",
}


def extract_schema_keyword(question: str) -> str:
    tokens = re.findall(r"[a-zA-Z_]+", question.lower())
    for token in reversed(tokens):
        if token not in STOPWORDS and len(token) >= 3:
            return token
    return question.strip()


def extract_business_term(question: str) -> str:
    normalized = question.lower()
    for key, payload in BUSINESS_DEFINITIONS.items():
        if key in normalized:
            return key
        if payload["term"].lower() in normalized:
            return key

    tokens = re.findall(r"[a-zA-Z_]+", normalized)
    for token in reversed(tokens):
        if token not in STOPWORDS and len(token) >= 3:
            return token
    return normalized.strip()


SQL_TEMPLATES = [
    (
        ["top categories", "top category", "category revenue"],
        """
        SELECT category_name_en, total_orders, total_revenue, avg_item_value
        FROM serving.fct_sales_by_category
        ORDER BY total_revenue DESC
        LIMIT 10
        """,
    ),
    (
        ["monthly", "monthly revenue", "monthly gmv", "monthly sales"],
        """
        SELECT month, total_orders, delivered_orders, gmv, avg_order_value
        FROM serving.kpi_monthly_sales
        ORDER BY month
        """,
    ),
    (
        ["delivery", "delay"],
        """
        SELECT order_month, avg_delivery_delay_days, late_delivery_rate
        FROM serving.delivery_performance_monthly
        ORDER BY order_month
        """,
    ),
]


def sql_from_question(question: str) -> str:
    normalized = question.strip().lower()
    if normalized.startswith("select") or normalized.startswith("with"):
        return question

    for keywords, query in SQL_TEMPLATES:
        if any(keyword in normalized for keyword in keywords):
            return query

    return """
    SELECT total_orders, delivered_orders, delivered_order_rate, gmv, avg_order_value
    FROM serving.kpi_overview
    """


def query_data_tool(question_or_sql: str, limit: int = 200) -> dict[str, Any]:
    sql_text = sql_from_question(question_or_sql)
    return service.query_data(sql_text=sql_text, limit=limit)
