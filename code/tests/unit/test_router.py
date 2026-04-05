from app.agent.router import classify_intent, route_for_intent


def test_classify_sql_query() -> None:
    assert classify_intent("SELECT * FROM serving.kpi_overview") == "sql_query"


def test_classify_schema_search() -> None:
    assert classify_intent("show table schema for payments") == "schema_search"


def test_classify_definition() -> None:
    assert classify_intent("what is gmv definition") == "business_definition"


def test_classify_kpi() -> None:
    assert classify_intent("monthly revenue trend") == "kpi_summary"


def test_route_for_intent() -> None:
    assert route_for_intent("kpi_summary") == "insight_agent"
