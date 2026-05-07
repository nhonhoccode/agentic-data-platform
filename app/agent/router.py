from __future__ import annotations

import re

SCHEMA_KEYWORDS = {"schema", "column", "table", "field", "metadata"}
DEFINITION_KEYWORDS = {"definition", "define", "meaning", "what is", "dinh nghia", "định nghĩa"}
KPI_KEYWORDS = {
    "kpi",
    "gmv",
    "aov",
    "revenue",
    "summary",
    "trend",
    "monthly",
    "doanh thu",
    "xu huong",
    "xu hướng",
    "thang",
    "tháng",
    "quy",
    "quý",
}
SQL_KEYWORDS = {
    "sql",
    "query",
    "select",
    "from",
    "where",
    "group by",
    "order by",
    "limit",
    "join",
    "truy van",
    "truy vấn",
    "danh sach",
    "danh sách",
    "đơn hàng",
    "don hang",
    "sản phẩm",
    "san pham",
    "doanh thu",
}
HELP_KEYWORDS = {"help", "what can you do", "làm được gì", "ban lam duoc gi", "capabilities", "commands"}
SMALLTALK_KEYWORDS = {
    "hi",
    "hello",
    "hey",
    "how are you",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
}
ANALYTICS_HINTS = {
    "order",
    "orders",
    "revenue",
    "sales",
    "gmv",
    "aov",
    "kpi",
    "truy van",
    "truy vấn",
    "don hang",
    "đơn hàng",
    "san pham",
    "sản phẩm",
    "doanh thu",
    "danh muc",
    "danh mục",
    "bao cao",
    "báo cáo",
    "thang",
    "tháng",
    "quy",
    "quý",
    "gan nhat",
    "gần nhất",
}


def _normalize(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return normalized


def _keyword_score(question: str, keywords: set[str]) -> int:
    return sum(1 for keyword in keywords if keyword in question)


def _looks_like_sql(question: str) -> bool:
    if re.match(r"^(select|with)\b", question):
        return True

    sql_clause_hits = sum(
        1
        for token in (
            " select ",
            " from ",
            " where ",
            " group by ",
            " order by ",
            " limit ",
            " join ",
        )
        if token in f" {question} "
    )
    return sql_clause_hits >= 2


def classify_intent(question: str) -> str:
    q = _normalize(question)
    if not q:
        return "chitchat"

    if _looks_like_sql(q):
        return "sql_query"

    if any(keyword in q for keyword in HELP_KEYWORDS):
        return "help_request"

    if any(keyword in q for keyword in ANALYTICS_HINTS):
        if any(keyword in q for keyword in {"schema", "column", "table", "metadata", "cột", "bảng"}):
            return "schema_search"
        if any(
            keyword in q
            for keyword in {
                "definition",
                "define",
                "dinh nghia",
                "định nghĩa",
                "meaning",
                "la gi",
                "là gì",
                "nghia la",
                "nghĩa là",
                "viet tat",
                "viết tắt",
                "what is",
                "what does",
            }
        ):
            return "business_definition"
        if any(keyword in q for keyword in {"danh muc", "danh mục", "category", "categories"}):
            return "sql_query"
        if any(keyword in q for keyword in {"kpi", "doanh thu", "gmv", "aov", "trend", "xu huong", "xu hướng"}):
            return "kpi_summary"
        return "sql_query"

    scores = {
        "schema_search": _keyword_score(q, SCHEMA_KEYWORDS),
        "business_definition": _keyword_score(q, DEFINITION_KEYWORDS),
        "kpi_summary": _keyword_score(q, KPI_KEYWORDS),
        "sql_query": _keyword_score(q, SQL_KEYWORDS),
    }

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]
    if best_score > 0:
        return best_intent

    if any(keyword in q for keyword in SMALLTALK_KEYWORDS):
        return "chitchat"

    # Short ambiguous text defaults to small talk.
    if len(q.split()) <= 4:
        return "chitchat"

    # Open natural-language requests default to agentic SQL intent.
    if re.match(r"^(show|list|find|get|give|tell|display)\b", q):
        return "sql_query"

    return "chitchat"


def route_for_intent(intent: str) -> str:
    mapping = {
        "sql_query": "sql_agent",
        "schema_search": "retrieval_agent",
        "business_definition": "retrieval_agent",
        "kpi_summary": "insight_agent",
        "help_request": "chat_agent",
        "chitchat": "chat_agent",
    }
    return mapping.get(intent, "chat_agent")
