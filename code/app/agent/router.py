from __future__ import annotations

SCHEMA_KEYWORDS = {"schema", "column", "table", "field", "metadata"}
DEFINITION_KEYWORDS = {"definition", "define", "meaning", "what is"}
KPI_KEYWORDS = {"kpi", "gmv", "aov", "revenue", "summary", "trend", "monthly"}


def classify_intent(question: str) -> str:
    q = question.strip().lower()

    if q.startswith("select") or q.startswith("with"):
        return "sql_query"

    if any(keyword in q for keyword in SCHEMA_KEYWORDS):
        return "schema_search"

    if any(keyword in q for keyword in DEFINITION_KEYWORDS):
        return "business_definition"

    if any(keyword in q for keyword in KPI_KEYWORDS):
        return "kpi_summary"

    return "sql_query"


def route_for_intent(intent: str) -> str:
    mapping = {
        "sql_query": "sql_agent",
        "schema_search": "retrieval_agent",
        "business_definition": "retrieval_agent",
        "kpi_summary": "insight_agent",
    }
    return mapping.get(intent, "sql_agent")
