from __future__ import annotations

import re
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agent.llm import llm_invoke_text
from app.agent.tools import sql_from_question
from app.db.sql_safety import UnsafeQueryError
from app.rag.retrieval import format_schema_context, retrieve_tables
from app.services.query_service import QueryService

MAX_FIX_ATTEMPTS = 3


class SQLState(TypedDict, total=False):
    question: str
    schema_hits: list[dict[str, Any]]
    schema_context: str
    sql: str
    error: str | None
    attempts: int
    history: list[dict[str, str]]
    raw_result: dict[str, Any]
    selected_tools: list[str]


_service = QueryService()


_SQL_PROMPT_TEMPLATE = """Bạn là chuyên gia SQL Postgres cho hệ thống phân tích thương mại điện tử Olist.
Sinh đúng 1 câu SELECT (hoặc CTE WITH ... SELECT) thỏa câu hỏi của người dùng.

Quy tắc cứng:
- Chỉ được đọc từ schema `marts.*` hoặc `serving.*`. KHÔNG dùng schema `raw.*` hay `staging.*`.
- KHÔNG dùng INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/GRANT/REVOKE/TRUNCATE.
- KHÔNG sinh nhiều statement, không dùng dấu ;.
- Nếu câu hỏi có thể dùng KPI có sẵn, ưu tiên `serving.kpi_overview`, `serving.kpi_monthly_sales`,
  `serving.fct_sales_by_category`, `serving.delivery_performance_monthly`.
- Trả lời CHỈ là câu SQL (không markdown, không giải thích).

Schema có sẵn (top kết quả từ vector search):
{schema_context}

Câu hỏi: {question}

SQL:"""


_SQL_FIX_PROMPT_TEMPLATE = """Câu SQL trước bị lỗi khi chạy trên Postgres. Hãy sửa để chạy được.

Câu hỏi gốc: {question}

Schema gợi ý:
{schema_context}

Lịch sử các lần thử trước (KHÔNG được lặp lại lỗi cũ):
{history}

SQL bị lỗi gần nhất:
{sql}

Lỗi gần nhất:
{error}

Hướng sửa: kiểm tra tên schema (chỉ marts/serving), tên cột, kiểu dữ liệu, JOIN keys.
Trả lời CHỈ là câu SQL đã sửa (không markdown, không giải thích)."""


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(chưa có)"
    lines = []
    for idx, h in enumerate(history, 1):
        lines.append(f"--- Attempt {idx} ---")
        lines.append(f"SQL: {h.get('sql', '')[:300]}")
        lines.append(f"Error: {h.get('error', '')[:200]}")
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    fence = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return text


def _table_selection_node(state: SQLState) -> SQLState:
    hits = retrieve_tables(state["question"], limit=6)
    return {
        **state,
        "schema_hits": hits,
        "schema_context": format_schema_context(hits),
        "attempts": state.get("attempts", 0),
        "selected_tools": ["table_selection"],
    }


def _query_generation_node(state: SQLState) -> SQLState:
    schema_context = state.get("schema_context") or "(không có context)"
    error = state.get("error")
    history = state.get("history", [])
    if error:
        prompt = _SQL_FIX_PROMPT_TEMPLATE.format(
            question=state["question"],
            schema_context=schema_context,
            sql=state.get("sql", ""),
            error=error,
            history=_format_history(history),
        )
    else:
        prompt = _SQL_PROMPT_TEMPLATE.format(
            question=state["question"],
            schema_context=schema_context,
        )

    sql_text = llm_invoke_text(prompt)
    if not sql_text:
        sql_text = sql_from_question(state["question"])

    cleaned = _strip_code_fence(sql_text)
    return {
        **state,
        "sql": cleaned,
        "selected_tools": [*state.get("selected_tools", []), "query_generation"],
    }


def _query_execution_node(state: SQLState) -> SQLState:
    sql_text = state.get("sql", "")
    if not sql_text:
        return {**state, "error": "empty_sql"}

    try:
        result = _service.query_data(sql_text=sql_text, limit=200)
        return {
            **state,
            "raw_result": result,
            "error": None,
            "selected_tools": [*state.get("selected_tools", []), "query_execution"],
        }
    except UnsafeQueryError as exc:
        return {**state, "error": f"unsafe_query: {exc}"}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"{type(exc).__name__}: {exc}"}


def _bug_fixing_node(state: SQLState) -> SQLState:
    history = list(state.get("history", []))
    history.append(
        {
            "sql": state.get("sql", ""),
            "error": state.get("error", ""),
        }
    )
    return {
        **state,
        "attempts": state.get("attempts", 0) + 1,
        "history": history,
        "selected_tools": [*state.get("selected_tools", []), "bug_fixing"],
    }


def _post_execution_router(state: SQLState) -> str:
    if not state.get("error"):
        return "ok"
    if state.get("attempts", 0) >= MAX_FIX_ATTEMPTS:
        return "give_up"
    return "fix"


def build_sql_graph() -> Any:
    graph = StateGraph(SQLState)
    graph.add_node("table_selection", _table_selection_node)
    graph.add_node("query_generation", _query_generation_node)
    graph.add_node("query_execution", _query_execution_node)
    graph.add_node("bug_fixing", _bug_fixing_node)

    graph.add_edge(START, "table_selection")
    graph.add_edge("table_selection", "query_generation")
    graph.add_edge("query_generation", "query_execution")

    graph.add_conditional_edges(
        "query_execution",
        _post_execution_router,
        {"ok": END, "fix": "bug_fixing", "give_up": END},
    )
    graph.add_edge("bug_fixing", "query_generation")

    return graph.compile()


_SQL_GRAPH = build_sql_graph()


def run_sql_graph(question: str) -> dict[str, Any]:
    initial: SQLState = {"question": question, "attempts": 0, "selected_tools": []}
    final = _SQL_GRAPH.invoke(initial)
    return {
        "sql": final.get("sql"),
        "raw_result": final.get("raw_result", {}),
        "error": final.get("error"),
        "attempts": final.get("attempts", 0),
        "selected_tools": final.get("selected_tools", []),
        "schema_hits": [
            h["payload"].get("fully_qualified")
            for h in final.get("schema_hits", [])
            if isinstance(h, dict) and h.get("payload")
        ],
    }
