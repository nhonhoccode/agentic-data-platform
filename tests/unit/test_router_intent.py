from app.agent.router import classify_intent


def test_business_definition_vietnamese_la_gi() -> None:
    assert classify_intent("GMV la gi") == "business_definition"
    assert classify_intent("GMV nghia la gi") == "business_definition"
    assert classify_intent("AOV viet tat tu gi") == "business_definition"


def test_kpi_summary_when_no_definition_phrasing() -> None:
    assert classify_intent("Cho tao xem KPI thang") == "kpi_summary"
    assert classify_intent("xu huong doanh thu") == "kpi_summary"


def test_sql_query_for_categories() -> None:
    assert classify_intent("doanh thu theo danh muc") == "sql_query"


def test_schema_search() -> None:
    assert classify_intent("schema cua bang orders") == "schema_search"


def test_help_request() -> None:
    assert classify_intent("ban lam duoc gi") == "help_request"
    assert classify_intent("/help") == "help_request"


def test_chitchat_short() -> None:
    assert classify_intent("hi") == "chitchat"
