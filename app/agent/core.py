from __future__ import annotations

import argparse
import asyncio
import contextvars
import enum
import json
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.config import get_settings
from app.observability import configure_langsmith

configure_langsmith()


class BlockReason(str, enum.Enum):
    """Why the agent short-circuited a web_search request with a canned answer."""

    TOGGLE_OFF_USER = "toggle_off_user"
    TOGGLE_OFF_ADMIN = "toggle_off_admin"
    OUT_OF_DOMAIN = "out_of_domain"
    SQL_EMPTY = "sql_empty"
    BLANK_QUERY = "blank_query"


_REFUSAL_TOGGLE_OFF_USER = (
    "Web search đang TẮT trong cài đặt của bạn. "
    "Bạn có thể bật lại trong panel cài đặt nếu muốn tra cứu thông tin trên Internet."
)
_REFUSAL_TOGGLE_OFF_ADMIN = (
    "Web search hiện chưa được quản trị viên kích hoạt (TAVILY_API_KEY trống hoặc WEB_SEARCH_ENABLED=false). "
    "Hãy báo admin để bật tính năng này."
)
_REFUSAL_OUT_OF_DOMAIN = (
    "Câu hỏi này nằm ngoài phạm vi Olist AI Data Platform (chuyên về ecommerce, KPI, data engineering). "
    "Mình tạm không tra cứu Internet để tiết kiệm quota — bạn có thể đặt câu hỏi gần với dữ liệu / phân tích kinh doanh hơn nhé."
)
_REFUSAL_SQL_EMPTY = (
    "Truy vấn dữ liệu nội bộ không có kết quả và web search đang tắt. "
    "Bạn có thể bật web search để mở rộng tìm kiếm ra Internet."
)
_REFUSAL_BLANK = (
    "Mình không nhận được câu hỏi web search hợp lệ. Bạn vui lòng nhập lại câu hỏi cụ thể hơn nhé."
)


def _set_block(
    state: dict[str, Any], message: str, reason: BlockReason
) -> dict[str, Any]:
    """Mutate state-update dict with a blocked_answer + blocked_reason."""
    state["blocked_answer"] = message
    state["blocked_reason"] = reason.value
    return state


def _clean_history_for_llm(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop history turns that were themselves blocked refusals — feeding
    them into the LLM rewriter would poison the standalone query."""
    cleaned: list[dict[str, Any]] = []
    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        meta = turn.get("metadata")
        if isinstance(meta, dict) and meta.get("blocked"):
            continue
        cleaned.append(turn)
    return cleaned


# ---------------------------------------------------------------------------
# Per-tool event emitter — wired by stream_workflow(), no-op in sync run_chat.
# ---------------------------------------------------------------------------
_TOOL_EMITTER: contextvars.ContextVar[Callable[[dict[str, Any]], None] | None] = (
    contextvars.ContextVar("tool_emitter", default=None)
)


def emit_tool(
    parent: str,
    tool: str,
    label: str,
    status: str,
    detail: str | None = None,
) -> None:
    """Push a `tool` SSE payload into the stream queue if a streaming workflow
    is active. Safe to call from anywhere (sub-graph nodes, helpers); no-op when
    called from the sync chat path."""
    cb = _TOOL_EMITTER.get()
    if cb is None:
        return
    try:
        cb(
            {
                "type": "tool",
                "parent": parent,
                "tool": tool,
                "label": label,
                "status": status,
                "detail": detail,
            }
        )
    except Exception:  # noqa: BLE001
        # Streaming must never break the agent execution.
        pass

from langgraph.graph import END, START, StateGraph  # noqa: E402

from app.agent.models import AgentState  # noqa: E402
from app.agent.router import classify_intent, route_for_intent  # noqa: E402
from app.agent.tools import (  # noqa: E402
    business_definition_tool,
    extract_business_term,
    extract_schema_keyword,
    kpi_summary_tool,
    query_data_tool,
    search_schema_tool,
)


_INTENT_PIPELINE = {
    "sql_query": ["sql_agent", "viz_agent"],
    "kpi_summary": ["insight_agent", "viz_agent", "time_series_agent", "analytic_agent"],
    "schema_search": ["retrieval_agent"],
    "business_definition": ["retrieval_agent"],
    "web_search": ["web_search_agent"],
    "help_request": ["chat_agent"],
    "chitchat": ["chat_agent"],
}


def _classify_node(state: AgentState) -> AgentState:
    intent = classify_intent(state["question"])
    pipeline = list(_INTENT_PIPELINE.get(intent, ["chat_agent"]))

    update: dict[str, Any] = {
        **state,
        "intent": intent,
        "route": route_for_intent(intent),
        "pending_agents": pipeline,
        "completed_agents": [],
        "iteration": 0,
        "warnings": state.get("warnings", []),
        "selected_tools": [],
        "sql": None,
    }

    # Toggle gating for web_search intent. Admin precedence first.
    if intent == "web_search":
        settings = get_settings()
        admin_on = bool(settings.web_search_enabled and settings.tavily_api_key)
        user_on = bool(state.get("web_search_enabled", False))
        if not admin_on:
            _set_block(update, _REFUSAL_TOGGLE_OFF_ADMIN, BlockReason.TOGGLE_OFF_ADMIN)
        elif not user_on:
            _set_block(update, _REFUSAL_TOGGLE_OFF_USER, BlockReason.TOGGLE_OFF_USER)

    return update


def _manager_node(state: AgentState) -> AgentState:
    return {**state, "iteration": state.get("iteration", 0) + 1}


def _manager_router(state: AgentState) -> str:
    pending = state.get("pending_agents") or []
    if state.get("iteration", 0) > 6:
        return "synthesize"
    if not pending:
        return "synthesize"
    return pending[0]


def _consume_agent(state: AgentState, name: str) -> dict[str, Any]:
    pending = list(state.get("pending_agents") or [])
    if pending and pending[0] == name:
        pending = pending[1:]
    completed = [*state.get("completed_agents", []), name]
    return {"pending_agents": pending, "completed_agents": completed}


def _maybe_queue_web_search_fallback(state_update: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """If SQL returned no rows and web search is enabled, push web_search_agent
    to the front of pending_agents so the manager routes there next.

    Respects both admin (settings.web_search_enabled + tavily key) and user
    (state.web_search_enabled) toggles. If admin allows but user toggled off
    and SQL is empty, we set a canned `blocked_answer` so the synth stage
    surfaces a friendly refusal instead of an empty result.
    """
    settings = get_settings()
    admin_on = bool(settings.web_search_enabled and settings.tavily_api_key)

    raw = state_update.get("raw_result") or {}
    row_count = 0
    if isinstance(raw, dict):
        row_count = raw.get("row_count") or 0
        if not row_count and isinstance(raw.get("data"), list):
            row_count = len(raw["data"])

    if row_count > 0:
        return state_update

    if not admin_on:
        # Admin disabled — leave SQL-empty as-is, do not block.
        return state_update

    user_on = bool(state.get("web_search_enabled", False))
    if not user_on:
        # SQL empty + user toggle off → friendly refusal, do not queue agent.
        _set_block(state_update, _REFUSAL_SQL_EMPTY, BlockReason.SQL_EMPTY)
        return state_update

    pending = list(state_update.get("pending_agents") or [])
    completed = state_update.get("completed_agents") or state.get("completed_agents", [])
    if "web_search_agent" in pending or "web_search_agent" in completed:
        return state_update

    pending.insert(0, "web_search_agent")
    warnings = list(state_update.get("warnings", []))
    warnings.append("sql_empty_fallback_to_web_search")
    state_update["pending_agents"] = pending
    state_update["warnings"] = warnings
    return state_update


def _sql_node(state: AgentState) -> AgentState:
    consume = _consume_agent(state, "sql_agent")
    try:
        from app.agent.sql.graph import run_sql_graph

        sub = run_sql_graph(state["question"])
        if sub.get("raw_result") and not sub.get("error"):
            confidence = 0.9 if sub.get("attempts", 0) == 0 else 0.75
            update = {
                **state,
                **consume,
                "selected_tools": [*state.get("selected_tools", []), *sub.get("selected_tools", [])],
                "sql": sub.get("sql"),
                "raw_result": sub.get("raw_result", {}),
                "confidence": confidence,
                "warnings": (
                    [*state.get("warnings", []), f"sql_self_correction_attempts={sub['attempts']}"]
                    if sub.get("attempts", 0) > 0
                    else state.get("warnings", [])
                ),
            }
            return _maybe_queue_web_search_fallback(update, state)

        warnings = list(state.get("warnings", []))
        if sub.get("error"):
            warnings.append(f"sql_subgraph_failed: {sub['error']}")
    except Exception as exc:  # noqa: BLE001
        warnings = [*state.get("warnings", []), f"sql_subgraph_unavailable: {exc}"]

    result = query_data_tool(state["question"], limit=200)
    update = {
        **state,
        **consume,
        "selected_tools": [*state.get("selected_tools", []), "query_data"],
        "sql": result["executed_sql"],
        "raw_result": result,
        "confidence": 0.82,
        "warnings": warnings,
    }
    return _maybe_queue_web_search_fallback(update, state)


def _retrieval_node(state: AgentState) -> AgentState:
    consume = _consume_agent(state, "retrieval_agent")
    selected = list(state.get("selected_tools", []))

    if state["intent"] == "schema_search":
        # Try RAG (Qdrant) first, fall back to live information_schema search.
        try:
            from app.rag.retrieval import retrieve_tables

            hits = retrieve_tables(state["question"], limit=5)
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            matches = [
                {
                    "table_schema": h["payload"].get("schema"),
                    "table_name": h["payload"].get("table"),
                    "columns": ", ".join(h["payload"].get("columns", [])[:8]),
                    "score": round(h.get("score", 0.0), 3),
                }
                for h in hits
            ]
            return {
                **state,
                **consume,
                "selected_tools": [*selected, "rag_schema_search"],
                "raw_result": {"matches": matches, "match_count": len(matches), "source": "rag"},
                "confidence": 0.88,
            }

        keyword = extract_schema_keyword(state["question"])
        result = search_schema_tool(keyword)
        return {
            **state,
            **consume,
            "selected_tools": [*selected, "search_schema"],
            "raw_result": result,
            "confidence": 0.85,
        }

    term = extract_business_term(state["question"])
    result = business_definition_tool(term)

    # If exact glossary lookup fails, try RAG glossary as backup.
    if not result.get("found"):
        try:
            from app.rag.retrieval import retrieve_glossary

            hits = retrieve_glossary(state["question"], limit=2)
        except Exception:  # noqa: BLE001
            hits = []
        if hits and hits[0].get("score", 0.0) >= 0.5:
            top = hits[0]["payload"]
            result = {
                "found": True,
                "definition": {
                    "term": top.get("term"),
                    "definition": top.get("definition"),
                    "formula": top.get("formula"),
                    "source_table": top.get("source_table"),
                },
                "source": "rag",
                "score": hits[0]["score"],
            }
            return {
                **state,
                **consume,
                "selected_tools": [*selected, "rag_glossary"],
                "raw_result": result,
                "confidence": 0.85,
            }

    return {
        **state,
        **consume,
        "selected_tools": [*selected, "get_business_definition"],
        "raw_result": result,
        "confidence": 0.9 if result.get("found") else 0.5,
    }


def _insight_node(state: AgentState) -> AgentState:
    consume = _consume_agent(state, "insight_agent")
    context = state.get("context", {})
    result = kpi_summary_tool(
        start_date=context.get("start_date"),
        end_date=context.get("end_date"),
    )
    return {
        **state,
        **consume,
        "selected_tools": [*state.get("selected_tools", []), "get_kpi_summary"],
        "raw_result": result,
        "confidence": 0.88,
    }


def _extract_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    for key in ("data", "series", "matches"):
        v = raw.get(key)
        if isinstance(v, list):
            return v
    return []


def _viz_node(state: AgentState) -> AgentState:
    from app.agent.viz_graph import run_viz_graph

    consume = _consume_agent(state, "viz_agent")
    rows = _extract_rows(state.get("raw_result") or {})

    if not rows:
        return {**state, **consume, "chart": None}

    sub = run_viz_graph(rows, state.get("question", ""))
    chart = sub.get("chart")
    selected = list(state.get("selected_tools", []))
    selected.extend(sub.get("selected_tools", []))

    warnings = list(state.get("warnings", []))
    if sub.get("attempts", 0) > 0:
        warnings.append(f"viz_self_correction_attempts={sub['attempts']}")

    return {
        **state,
        **consume,
        "chart": chart,
        "selected_tools": selected,
        "warnings": warnings,
    }


def _analytic_node(state: AgentState) -> AgentState:
    from app.agent.analytic_graph import run_analytic_graph

    consume = _consume_agent(state, "analytic_agent")
    raw = state.get("raw_result") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        if isinstance(raw.get("series"), list):
            rows = raw["series"]
        elif isinstance(raw.get("data"), list):
            rows = raw["data"]

    sub = run_analytic_graph(rows, state.get("question", ""))
    branch = sub.get("branch", "other")
    branch_analytics = sub.get("analytics", {}) or {}

    # Merge with existing analytics so multiple agents (time_series + analytic) compose.
    merged = dict(state.get("analytics") or {})
    merged.update(branch_analytics)

    return {
        **state,
        **consume,
        "analytics": merged,
        "selected_tools": [
            *state.get("selected_tools", []),
            f"analytic_{branch}",
        ],
    }


def _time_series_node(state: AgentState) -> AgentState:
    from app.agent.analytic import time_series_summary

    consume = _consume_agent(state, "time_series_agent")
    raw = state.get("raw_result") or {}
    rows: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        if isinstance(raw.get("series"), list):
            rows = raw["series"]
        elif isinstance(raw.get("data"), list):
            rows = raw["data"]

    summary = time_series_summary(rows)
    merged = dict(state.get("analytics") or {})
    merged["time_series"] = summary

    return {
        **state,
        **consume,
        "analytics": merged,
        "selected_tools": [*state.get("selected_tools", []), "time_series"],
    }


def _chat_node(state: AgentState) -> AgentState:
    consume = _consume_agent(state, "chat_agent")
    return {
        **state,
        **consume,
        "raw_result": {"message_type": "chat", "question": state["question"]},
        "confidence": 0.7,
    }


_QUERY_REWRITE_PROMPT = """Bạn nhận hội thoại trước và câu hỏi mới. Câu mới có thể mơ hồ \
(viết tắt, sai chính tả, dùng "nó/cái này/này", reference tới chủ thể đã nói trước).
Hãy rewrite thành 1 câu search độc lập (standalone) bằng tiếng Việt, giữ ngữ cảnh từ hội thoại \
và sửa chính tả hiển nhiên. KHÔNG thêm thông tin không có trong hội thoại.
Trả lời CHỈ là 1 câu search rewritten, không markdown, không giải thích, không quote.

Hội thoại trước:
{history}

Câu hỏi mới: {question}

Câu search rewritten:"""


def _rewrite_search_query(question: str, history: list[dict[str, Any]]) -> tuple[str, bool]:
    """Standalone-query rewriting via LLM. Returns (query, was_rewritten).

    No-op when there's no history or when LLM is unavailable — falls back to
    the literal question. Never returns an empty string.
    """
    history = _clean_history_for_llm(list(history or []))
    if not history:
        return question, False

    from app.agent.llm import llm_invoke_text

    history_lines: list[str] = []
    for turn in history[-6:]:
        role = (turn.get("role") or "").strip()
        content = (turn.get("content") or "").strip()
        if role and content:
            history_lines.append(f"{role.upper()}: {content[:400]}")
    if not history_lines:
        return question, False

    prompt = _QUERY_REWRITE_PROMPT.format(
        history="\n".join(history_lines), question=question
    )
    rewritten = llm_invoke_text(prompt)
    if not rewritten:
        return question, False
    cleaned = rewritten.strip().strip('"').strip("'")
    cleaned = cleaned.splitlines()[0].strip() if cleaned else ""
    if not cleaned or cleaned.lower() == question.strip().lower():
        return question, False
    return cleaned, True


def _web_search_node(state: AgentState) -> AgentState:
    """Web search node with new ordering:

    a. blocked_answer already set upstream → emit done, return.
    b. raw question blank → BLANK_QUERY block.
    c. classify_in_domain → OUT_OF_DOMAIN block on False.
    d. _rewrite_search_query (history-aware), falls back to raw.
    e. Tavily call.
    """
    from app.agent.tools import web_search_tool

    consume = _consume_agent(state, "web_search_agent")
    question = state.get("question") or ""

    # (a) Already blocked upstream — short-circuit, emit neutral done.
    if state.get("blocked_answer"):
        emit_tool(
            "web_search_agent",
            "tavily_search",
            "Web search bỏ qua (đã chặn trước)",
            "done",
            detail=str(state.get("blocked_reason") or "blocked")[:120],
        )
        return {
            **state,
            **consume,
            "selected_tools": [*state.get("selected_tools", []), "tavily_search"],
            "web_search": {
                "query": question,
                "answer": None,
                "results": [],
                "count": 0,
                "error": "blocked",
                "reason": state.get("blocked_reason"),
            },
            "confidence": 0.4,
        }

    # (b) Blank query guard.
    if not question.strip():
        emit_tool(
            "web_search_agent",
            "tavily_search",
            "Câu hỏi trống — bỏ qua web search",
            "done",
        )
        update = {
            **state,
            **consume,
            "selected_tools": [*state.get("selected_tools", []), "tavily_search"],
            "web_search": {
                "query": question,
                "answer": None,
                "results": [],
                "count": 0,
                "error": "blank_query",
            },
            "confidence": 0.3,
        }
        _set_block(update, _REFUSAL_BLANK, BlockReason.BLANK_QUERY)
        return update

    # (c) In-domain classification. Skipped when the user clicked the
    # "Vẫn tra cứu Internet" CTA — force_web_search bypasses the gate so
    # off-topic prompts can opt out of the refusal explicitly.
    if state.get("force_web_search"):
        emit_tool(
            "web_search_agent",
            "domain_filter",
            "Bỏ qua domain filter (force search)",
            "done",
            detail="force_web_search=true",
        )
        in_domain, dom_reason = True, "force_bypass"
    else:
        emit_tool(
            "web_search_agent",
            "domain_filter",
            "Kiểm tra câu hỏi có thuộc domain ecommerce/data hay không",
            "start",
        )
        try:
            from app.agent.domain_filter import classify_in_domain

            in_domain, dom_reason = classify_in_domain(question)
        except Exception as exc:  # noqa: BLE001
            # Domain filter must never crash the agent — fail-closed on exception.
            in_domain, dom_reason = False, f"error:{type(exc).__name__}"

    if not in_domain:
        emit_tool(
            "web_search_agent",
            "domain_filter",
            "Câu hỏi ngoài domain — bỏ qua web search",
            "done",
            detail=dom_reason[:120],
        )
        update = {
            **state,
            **consume,
            "selected_tools": [*state.get("selected_tools", []), "tavily_search"],
            "web_search": {
                "query": question,
                "answer": None,
                "results": [],
                "count": 0,
                "error": "out_of_domain",
                "reason": dom_reason,
            },
            "warnings": [*state.get("warnings", []), f"out_of_domain: {dom_reason}"],
            "confidence": 0.3,
        }
        _set_block(update, _REFUSAL_OUT_OF_DOMAIN, BlockReason.OUT_OF_DOMAIN)
        return update

    emit_tool(
        "web_search_agent",
        "domain_filter",
        "Câu hỏi thuộc domain — tiếp tục search",
        "done",
        detail=dom_reason[:120],
    )

    # (d) History-aware rewrite. Never returns empty — falls back to raw.
    history = state.get("history") or []
    search_query = question
    if history:
        emit_tool(
            "web_search_agent",
            "query_rewrite",
            "Rewrite câu hỏi theo lịch sử hội thoại",
            "start",
        )
        rewritten, was_rewritten = _rewrite_search_query(question, history)
        if was_rewritten and rewritten.strip():
            search_query = rewritten
            emit_tool(
                "web_search_agent",
                "query_rewrite",
                "Đã rewrite thành câu search độc lập",
                "done",
                detail=rewritten[:200],
            )
        else:
            emit_tool(
                "web_search_agent",
                "query_rewrite",
                "Giữ nguyên câu hỏi (không cần rewrite)",
                "done",
            )

    if not search_query.strip():
        search_query = question

    # (e) Tavily call.
    settings = get_settings()
    emit_tool(
        "web_search_agent",
        "tavily_search",
        "Đang search trên Internet (Tavily)",
        "start",
        detail=search_query[:160],
    )
    result = web_search_tool(search_query, max_results=settings.web_search_max_results)

    if result.get("error"):
        emit_tool(
            "web_search_agent",
            "tavily_search",
            "Search lỗi",
            "error",
            detail=str(result.get("error"))[:200],
        )
        return {
            **state,
            **consume,
            "selected_tools": [*state.get("selected_tools", []), "tavily_search"],
            "web_search": result,
            "warnings": [*state.get("warnings", []), f"web_search_error: {result.get('error')}"],
            "confidence": 0.4,
        }

    emit_tool(
        "web_search_agent",
        "tavily_search",
        f"Search xong ({result.get('count', 0)} kết quả)",
        "done",
        detail=(result.get("answer") or "")[:200] or None,
    )
    return {
        **state,
        **consume,
        "selected_tools": [*state.get("selected_tools", []), "tavily_search"],
        "web_search": result,
        "confidence": 0.75,
    }


def _fallback_summarize(result: dict[str, Any], intent: str) -> str:
    if intent == "help_request":
        return (
            "Mình có thể hỗ trợ KPI, tra cứu schema, giải thích business definition "
            "và truy vấn SQL chỉ đọc. Bạn hỏi tự nhiên hoặc dùng /help để xem lệnh."
        )
    if intent == "chitchat":
        return (
            "Mình đang online. Bạn có thể hỏi về KPI, xu hướng doanh thu, schema "
            "hoặc business term, mình sẽ tự route đúng tool."
        )
    if intent == "schema_search":
        return f"Đã tìm thấy {result.get('match_count', 0)} kết quả schema theo từ khóa."
    if intent == "business_definition":
        if result.get("found"):
            definition = result["definition"]
            return f"{definition['term']}: {definition['definition']}"
        return "Không tìm thấy định nghĩa. Bạn thử một thuật ngữ khác nhé."
    if intent == "kpi_summary":
        overview = result.get("overview", {})
        return (
            "Đã tải KPI: "
            f"orders={overview.get('total_orders')}, gmv={overview.get('gmv')}, "
            f"delivered_rate={overview.get('delivered_order_rate')}"
        )

    if intent == "web_search":
        ws = result if isinstance(result, dict) and "results" in result else result.get("web_search") if isinstance(result, dict) else None
        if isinstance(ws, dict):
            if ws.get("error") == "disabled":
                return "Web search hiện đang tắt. Bật bằng cách điền TAVILY_API_KEY trong .env."
            if ws.get("error"):
                return f"Search lỗi: {ws.get('error')}"
            count = ws.get("count", 0)
            if count == 0:
                return "Search không trả về kết quả nào."
            return ws.get("answer") or f"Tìm thấy {count} nguồn liên quan."
        return "Đã thực hiện web search."

    rows = result.get("row_count", 0)
    return f"Truy vấn thành công, trả về {rows} dòng."


def _build_summarization_llm() -> Any | None:
    from app.agent.llm import get_chat_llm

    return get_chat_llm()


def _format_history_for_prompt(history: list[dict[str, Any]]) -> str:
    if not history:
        return ""
    turns = []
    for h in history[-6:]:
        role = h.get("role", "")
        content = (h.get("content", "") or "").strip()
        if role and content:
            turns.append(f"{role.upper()}: {content[:300]}")
    if not turns:
        return ""
    return "\n--- Bối cảnh hội thoại trước ---\n" + "\n".join(turns) + "\n---"


def _build_synthesis_prompt(state: AgentState) -> str:
    intent = state.get("intent", "")
    question = state.get("question", "")
    history_str = _format_history_for_prompt(state.get("history", []))
    result_payload = json.dumps(state.get("raw_result", {}), default=str)[:5000]

    if intent == "web_search":
        ws = state.get("web_search") or {}
        return (
            "Bạn là trợ lý phân tích dữ liệu. Trả lời tiếng Việt, ngắn gọn 3-5 câu. "
            "Dựa CHÍNH XÁC vào kết quả web search dưới đây để trả lời câu hỏi. "
            "Trích dẫn ngắn (tên trang) khi cần. Nếu kết quả không liên quan thì nói thẳng. "
            f"{history_str}"
            f"Câu hỏi: {question}\n"
            f"Web search payload: {json.dumps(ws, default=str, ensure_ascii=False)[:5000]}"
        )

    if intent == "help_request":
        return (
            "Bạn là trợ lý phân tích dữ liệu thương mại điện tử. "
            "Luôn trả lời bằng tiếng Việt tự nhiên, ngắn gọn, dễ hiểu. "
            "Hãy mô tả bot làm được gì và đưa ra 3 ví dụ thực tế. "
            "Không hỏi ngược người dùng để chọn lựa. "
            f"{history_str}"
            f"Câu hỏi người dùng: {question}"
        )
    if intent == "chitchat":
        return (
            "Bạn là trợ lý phân tích dữ liệu thương mại điện tử. "
            "Luôn trả lời bằng tiếng Việt trong 2-4 câu tự nhiên. "
            "Giọng điệu thân thiện, nêu ngắn gọn khả năng của bạn. "
            "Không hỏi ngược người dùng hoặc ép người dùng chọn lựa. "
            f"{history_str}"
            f"Câu hỏi người dùng: {question}"
        )
    return (
        "Bạn là trợ lý phân tích dữ liệu. "
        "Luôn trả lời bằng tiếng Việt, tóm tắt kết quả trong tối đa 4 câu. "
        "Nếu đã có đủ dữ liệu thì trả kết quả trực tiếp, không hỏi lại. "
        f"{history_str}"
        f"Câu hỏi người dùng: {question}. Intent={intent}. Kết quả={result_payload}"
    )


def _maybe_llm_summarize(state: AgentState) -> str | None:
    try:
        import concurrent.futures

        llm = _build_summarization_llm()
        if llm is None:
            return None

        prompt = _build_synthesis_prompt(state)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(llm.invoke, prompt)
            try:
                response = future.result(timeout=20)
            except concurrent.futures.TimeoutError:
                return None
        content = getattr(response, "content", "")
        return str(content) if content else None
    except Exception:
        return None


def _synthesize_node(state: AgentState) -> AgentState:
    # Short-circuit: if upstream set a canned refusal, use it verbatim.
    blocked = state.get("blocked_answer")
    if blocked:
        return {
            **state,
            "result_summary": blocked,
            "warnings": state.get("warnings", []),
        }

    llm_summary = _maybe_llm_summarize(state)
    summary = llm_summary or _fallback_summarize(state.get("raw_result", {}), state["intent"])

    return {
        **state,
        "result_summary": summary,
        "warnings": state.get("warnings", []),
    }


def _build_graph_common(include_synthesize: bool) -> Any:
    graph = StateGraph(AgentState)
    graph.add_node("classify", _classify_node)
    graph.add_node("manager", _manager_node)
    graph.add_node("sql_agent", _sql_node)
    graph.add_node("retrieval_agent", _retrieval_node)
    graph.add_node("insight_agent", _insight_node)
    graph.add_node("viz_agent", _viz_node)
    graph.add_node("analytic_agent", _analytic_node)
    graph.add_node("time_series_agent", _time_series_node)
    graph.add_node("chat_agent", _chat_node)
    graph.add_node("web_search_agent", _web_search_node)
    if include_synthesize:
        graph.add_node("synthesize", _synthesize_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "manager")
    graph.add_conditional_edges(
        "manager",
        _manager_router,
        {
            "sql_agent": "sql_agent",
            "retrieval_agent": "retrieval_agent",
            "insight_agent": "insight_agent",
            "viz_agent": "viz_agent",
            "analytic_agent": "analytic_agent",
            "time_series_agent": "time_series_agent",
            "chat_agent": "chat_agent",
            "web_search_agent": "web_search_agent",
            "synthesize": "synthesize" if include_synthesize else END,
        },
    )
    for agent in (
        "sql_agent",
        "retrieval_agent",
        "insight_agent",
        "viz_agent",
        "analytic_agent",
        "time_series_agent",
        "chat_agent",
        "web_search_agent",
    ):
        graph.add_edge(agent, "manager")
    if include_synthesize:
        graph.add_edge("synthesize", END)

    return graph.compile()


def build_graph() -> Any:
    return _build_graph_common(include_synthesize=True)


_WORKFLOW = build_graph()
_WORKFLOW_STREAM = _build_graph_common(include_synthesize=False)


def run_workflow(
    question: str,
    context: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    web_search_enabled: bool = False,
    force_web_search: bool = False,
) -> dict[str, Any]:
    initial_state: AgentState = {
        "question": question,
        "context": context or {},
        "warnings": [],
        "history": list(history or []),
        "web_search_enabled": bool(web_search_enabled) or bool(force_web_search),
        "force_web_search": bool(force_web_search),
    }
    result = _WORKFLOW.invoke(initial_state)

    return {
        "intent": result.get("intent", "unknown"),
        "selected_tools": result.get("selected_tools", []),
        "sql": result.get("sql"),
        "result_summary": result.get("result_summary", "Chưa tạo được tóm tắt."),
        "confidence": float(result.get("confidence", 0.5)),
        "warnings": result.get("warnings", []),
        "raw_result": result.get("raw_result", {}),
        "chart": result.get("chart"),
        "analytics": result.get("analytics"),
        "web_search": result.get("web_search"),
        "completed_agents": result.get("completed_agents", []),
        "web_search_enabled": bool(web_search_enabled),
        "blocked_reason": result.get("blocked_reason"),
    }


_NODE_LABELS = {
    "classify": "Đang phân loại câu hỏi",
    "manager": "Manager đang điều phối",
    "sql_agent": "SQL agent: tra cứu dữ liệu",
    "retrieval_agent": "Retrieval agent: tra schema/định nghĩa",
    "insight_agent": "Insight agent: tổng hợp KPI",
    "viz_agent": "Viz agent: dựng biểu đồ",
    "analytic_agent": "Analytic agent: phân tích",
    "time_series_agent": "Time-series agent: trend",
    "chat_agent": "Chat agent: chuẩn bị phản hồi",
    "web_search_agent": "Web search agent: tìm trên Internet",
    "synthesize": "Đang tóm tắt kết quả",
}


_SENTINEL = object()


async def stream_workflow(
    question: str,
    context: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
    web_search_enabled: bool = False,
    force_web_search: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Run sync LangGraph in a worker thread, stream events via asyncio.Queue.

    Critical for SSE: sync sub-graphs (DB queries, LLM calls, fastembed) would
    otherwise block the asyncio event loop and prevent SSE flush.

    Synthesis is performed AFTER the graph completes, using llm.stream() so
    tokens are emitted as `token` events for true real-time UX. Falls back to
    a single `final` block with template text when LLM is unavailable.

    `web_search_enabled` mirrors the per-user toggle from the chat client. It
    is plumbed into initial_state and gates `_classify_node` /
    `_maybe_queue_web_search_fallback`.
    """
    initial_state: AgentState = {
        "question": question,
        "context": context or {},
        "warnings": [],
        "history": list(history or []),
        # Force-search implies user opted to bypass the domain gate AND obviously
        # wants web search enabled — collapse both into one flag for the agent.
        "web_search_enabled": bool(web_search_enabled) or bool(force_web_search),
        "force_web_search": bool(force_web_search),
    }
    final_state: dict[str, Any] = {}
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def queue_put(payload: dict[str, Any]) -> None:
        # Called from the producer thread. asyncio.Queue is not thread-safe, so
        # we hop back to the event loop via run_coroutine_threadsafe.
        asyncio.run_coroutine_threadsafe(queue.put(payload), loop).result()

    def producer() -> None:
        # Set the per-tool emitter for this thread so sub-graph nodes can push
        # `tool` events into the same SSE stream. Cleared on exit.
        token = _TOOL_EMITTER.set(queue_put)
        try:
            for event in _WORKFLOW_STREAM.stream(initial_state, stream_mode="updates"):
                for node_name, node_state in event.items():
                    if not isinstance(node_state, dict):
                        continue
                    final_state.update(node_state)
                    payload = {
                        "type": "step",
                        "node": node_name,
                        "label": _NODE_LABELS.get(node_name, node_name),
                        "intent": final_state.get("intent"),
                        "selected_tools": list(final_state.get("selected_tools", [])),
                    }
                    queue_put(payload)
        except Exception as exc:  # noqa: BLE001
            queue_put({"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
        finally:
            _TOOL_EMITTER.reset(token)
            queue_put(_SENTINEL)

    worker = threading.Thread(target=producer, daemon=True)
    worker.start()

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        yield item

    yield {
        "type": "step",
        "node": "synthesize",
        "label": _NODE_LABELS.get("synthesize", "synthesize"),
        "intent": final_state.get("intent"),
        "selected_tools": list(final_state.get("selected_tools", [])),
    }

    accumulated_text = ""
    async for token in _stream_synthesis(final_state, loop):
        accumulated_text += token
        yield {"type": "token", "text": token}

    if not accumulated_text.strip():
        # Prefer the canned blocked_answer over a generic fallback.
        blocked = final_state.get("blocked_answer")
        if blocked:
            accumulated_text = blocked
        else:
            accumulated_text = _fallback_summarize(
                final_state.get("raw_result", {}), final_state.get("intent", "")
            )

    yield {
        "type": "final",
        "intent": final_state.get("intent", "unknown"),
        "selected_tools": final_state.get("selected_tools", []),
        "sql": final_state.get("sql"),
        "result_summary": accumulated_text or "Chưa tạo được tóm tắt.",
        "confidence": float(final_state.get("confidence", 0.5)),
        "warnings": final_state.get("warnings", []),
        "raw_result": final_state.get("raw_result", {}),
        "chart": final_state.get("chart"),
        "analytics": final_state.get("analytics"),
        "web_search": final_state.get("web_search"),
        "completed_agents": final_state.get("completed_agents", []),
        "web_search_enabled": bool(web_search_enabled),
        "blocked_reason": final_state.get("blocked_reason"),
    }


async def _stream_synthesis(
    state: dict[str, Any], loop: asyncio.AbstractEventLoop
) -> AsyncIterator[str]:
    """Bridge sync llm.stream() into async token iterator. Empty iter if no LLM.

    If `state["blocked_answer"]` is set, skip the LLM entirely and stream
    the canned refusal verbatim (24-char chunks, 20ms apart) so the UI still
    sees a typing animation.
    """
    blocked = state.get("blocked_answer")
    if blocked:
        text = str(blocked)
        chunk = 24
        for i in range(0, len(text), chunk):
            yield text[i : i + chunk]
            await asyncio.sleep(0.02)
        return

    llm = _build_summarization_llm()
    if llm is None:
        return

    prompt = _build_synthesis_prompt(state)
    chunk_queue: asyncio.Queue = asyncio.Queue()

    def stream_producer() -> None:
        try:
            for chunk in llm.stream(prompt):
                text = getattr(chunk, "content", "") or ""
                if text:
                    asyncio.run_coroutine_threadsafe(chunk_queue.put(text), loop).result()
        except Exception as exc:  # noqa: BLE001
            asyncio.run_coroutine_threadsafe(
                chunk_queue.put({"__error__": f"{type(exc).__name__}: {exc}"}), loop
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(chunk_queue.put(_SENTINEL), loop).result()

    worker = threading.Thread(target=stream_producer, daemon=True)
    worker.start()

    while True:
        item = await chunk_queue.get()
        if item is _SENTINEL:
            return
        if isinstance(item, dict) and "__error__" in item:
            return
        yield item


def cli_run() -> None:
    parser = argparse.ArgumentParser(description="Run multi-agent workflow from terminal")
    parser.add_argument("question", type=str, help="Natural-language analytics question")
    args = parser.parse_args()

    result = run_workflow(args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    cli_run()
