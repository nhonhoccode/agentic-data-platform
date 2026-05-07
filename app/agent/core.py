from __future__ import annotations

import argparse
import asyncio
import json
import threading
from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings
from app.observability import configure_langsmith

configure_langsmith()

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
    "help_request": ["chat_agent"],
    "chitchat": ["chat_agent"],
}


def _classify_node(state: AgentState) -> AgentState:
    intent = classify_intent(state["question"])
    pipeline = list(_INTENT_PIPELINE.get(intent, ["chat_agent"]))
    return {
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


def _sql_node(state: AgentState) -> AgentState:
    consume = _consume_agent(state, "sql_agent")
    try:
        from app.agent.sql.graph import run_sql_graph

        sub = run_sql_graph(state["question"])
        if sub.get("raw_result") and not sub.get("error"):
            confidence = 0.9 if sub.get("attempts", 0) == 0 else 0.75
            return {
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

        warnings = list(state.get("warnings", []))
        if sub.get("error"):
            warnings.append(f"sql_subgraph_failed: {sub['error']}")
    except Exception as exc:  # noqa: BLE001
        warnings = [*state.get("warnings", []), f"sql_subgraph_unavailable: {exc}"]

    result = query_data_tool(state["question"], limit=200)
    return {
        **state,
        **consume,
        "selected_tools": [*state.get("selected_tools", []), "query_data"],
        "sql": result["executed_sql"],
        "raw_result": result,
        "confidence": 0.82,
        "warnings": warnings,
    }


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


def _maybe_llm_summarize(state: AgentState) -> str | None:
    try:
        import concurrent.futures

        llm = _build_summarization_llm()
        if llm is None:
            return None

        intent = state.get("intent", "")
        question = state.get("question", "")
        history_str = _format_history_for_prompt(state.get("history", []))
        result_payload = json.dumps(state.get("raw_result", {}), default=str)[:5000]

        if intent == "help_request":
            prompt = (
                "Bạn là trợ lý phân tích dữ liệu thương mại điện tử. "
                "Luôn trả lời bằng tiếng Việt tự nhiên, ngắn gọn, dễ hiểu. "
                "Hãy mô tả bot làm được gì và đưa ra 3 ví dụ thực tế. "
                "Không hỏi ngược người dùng để chọn lựa. "
                f"{history_str}"
                f"Câu hỏi người dùng: {question}"
            )
        elif intent == "chitchat":
            prompt = (
                "Bạn là trợ lý phân tích dữ liệu thương mại điện tử. "
                "Luôn trả lời bằng tiếng Việt trong 2-4 câu tự nhiên. "
                "Giọng điệu thân thiện, nêu ngắn gọn khả năng của bạn. "
                "Không hỏi ngược người dùng hoặc ép người dùng chọn lựa. "
                f"{history_str}"
                f"Câu hỏi người dùng: {question}"
            )
        else:
            prompt = (
                "Bạn là trợ lý phân tích dữ liệu. "
                "Luôn trả lời bằng tiếng Việt, tóm tắt kết quả trong tối đa 4 câu. "
                "Nếu đã có đủ dữ liệu thì trả kết quả trực tiếp, không hỏi lại. "
                f"{history_str}"
                f"Câu hỏi người dùng: {question}. Intent={intent}. Kết quả={result_payload}"
            )

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
    llm_summary = _maybe_llm_summarize(state)
    summary = llm_summary or _fallback_summarize(state.get("raw_result", {}), state["intent"])

    return {
        **state,
        "result_summary": summary,
        "warnings": state.get("warnings", []),
    }


def build_graph() -> Any:
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
            "synthesize": "synthesize",
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
    ):
        graph.add_edge(agent, "manager")
    graph.add_edge("synthesize", END)

    return graph.compile()


_WORKFLOW = build_graph()


def run_workflow(
    question: str,
    context: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    initial_state: AgentState = {
        "question": question,
        "context": context or {},
        "warnings": [],
        "history": list(history or []),
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
        "completed_agents": result.get("completed_agents", []),
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
    "synthesize": "Đang tóm tắt kết quả",
}


_SENTINEL = object()


async def stream_workflow(
    question: str,
    context: dict[str, Any] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Run sync LangGraph in a worker thread, stream events via asyncio.Queue.

    Critical for SSE: sync sub-graphs (DB queries, LLM calls, fastembed) would
    otherwise block the asyncio event loop and prevent SSE flush.
    """
    initial_state: AgentState = {
        "question": question,
        "context": context or {},
        "warnings": [],
        "history": list(history or []),
    }
    final_state: dict[str, Any] = {}
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer() -> None:
        try:
            for event in _WORKFLOW.stream(initial_state, stream_mode="updates"):
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
                    asyncio.run_coroutine_threadsafe(queue.put(payload), loop).result()
        except Exception as exc:  # noqa: BLE001
            asyncio.run_coroutine_threadsafe(
                queue.put({"type": "error", "detail": f"{type(exc).__name__}: {exc}"}),
                loop,
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(_SENTINEL), loop).result()

    worker = threading.Thread(target=producer, daemon=True)
    worker.start()

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break
        yield item

    yield {
        "type": "final",
        "intent": final_state.get("intent", "unknown"),
        "selected_tools": final_state.get("selected_tools", []),
        "sql": final_state.get("sql"),
        "result_summary": final_state.get("result_summary", "Chưa tạo được tóm tắt."),
        "confidence": float(final_state.get("confidence", 0.5)),
        "warnings": final_state.get("warnings", []),
        "raw_result": final_state.get("raw_result", {}),
        "chart": final_state.get("chart"),
        "analytics": final_state.get("analytics"),
        "completed_agents": final_state.get("completed_agents", []),
    }


def cli_run() -> None:
    parser = argparse.ArgumentParser(description="Run multi-agent workflow from terminal")
    parser.add_argument("question", type=str, help="Natural-language analytics question")
    args = parser.parse_args()

    result = run_workflow(args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    cli_run()
