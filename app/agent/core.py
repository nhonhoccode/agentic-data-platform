from __future__ import annotations

import argparse
import json
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.models import AgentState
from app.agent.router import classify_intent, route_for_intent
from app.agent.tools import (
    business_definition_tool,
    extract_business_term,
    extract_schema_keyword,
    kpi_summary_tool,
    query_data_tool,
    search_schema_tool,
)
from app.config import get_settings


def _classify_node(state: AgentState) -> AgentState:
    intent = classify_intent(state["question"])
    route = route_for_intent(intent)

    return {
        **state,
        "intent": intent,
        "route": route,
        "warnings": state.get("warnings", []),
        "selected_tools": [],
        "sql": None,
    }


def _route_selector(state: AgentState) -> str:
    return state["route"]


def _sql_node(state: AgentState) -> AgentState:
    result = query_data_tool(state["question"], limit=200)
    return {
        **state,
        "selected_tools": ["query_data"],
        "sql": result["executed_sql"],
        "raw_result": result,
        "confidence": 0.82,
    }


def _retrieval_node(state: AgentState) -> AgentState:
    if state["intent"] == "schema_search":
        keyword = extract_schema_keyword(state["question"])
        result = search_schema_tool(keyword)
        return {
            **state,
            "selected_tools": ["search_schema"],
            "raw_result": result,
            "confidence": 0.85,
        }

    term = extract_business_term(state["question"])
    result = business_definition_tool(term)
    return {
        **state,
        "selected_tools": ["get_business_definition"],
        "raw_result": result,
        "confidence": 0.9 if result.get("found") else 0.5,
    }


def _insight_node(state: AgentState) -> AgentState:
    context = state.get("context", {})
    result = kpi_summary_tool(
        start_date=context.get("start_date"),
        end_date=context.get("end_date"),
    )
    return {
        **state,
        "selected_tools": ["get_kpi_summary"],
        "raw_result": result,
        "confidence": 0.88,
    }


def _chat_node(state: AgentState) -> AgentState:
    return {
        **state,
        "selected_tools": [],
        "raw_result": {
            "message_type": "chat",
            "question": state["question"],
        },
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
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()

    if provider in {"", "none", "off", "disabled"}:
        return None

    if provider == "gemini":
        if not settings.gemini_api_key:
            return None

        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.model_api_base or "gemini-2.0-flash",
            google_api_key=settings.gemini_api_key,
            temperature=settings.temperature,
        )

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            return None

        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.model_api_base or "deepseek-chat",
            api_key=settings.deepseek_api_key,
            base_url=settings.base_url or "https://api.deepseek.com/v1",
            temperature=settings.temperature,
        )

    if provider in {"self_host", "openai_compatible"}:
        if not (settings.openai_api_key and settings.base_url and settings.model_api_base):
            return None

        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": settings.model_api_base,
            "api_key": settings.openai_api_key,
            "base_url": settings.base_url,
            "temperature": settings.temperature,
        }
        if not settings.llm_enable_thinking:
            kwargs["extra_body"] = {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            }

        return ChatOpenAI(**kwargs)

    if provider == "openai":
        if not settings.openai_api_key:
            return None

        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {
            "model": settings.openai_model or "gpt-4o-mini",
            "api_key": settings.openai_api_key,
            "temperature": settings.temperature,
        }
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        return ChatOpenAI(**kwargs)

    return None


def _maybe_llm_summarize(state: AgentState) -> str | None:
    try:
        llm = _build_summarization_llm()
        if llm is None:
            return None

        intent = state.get("intent", "")
        question = state.get("question", "")
        result_payload = json.dumps(state.get("raw_result", {}), default=str)[:5000]

        if intent == "help_request":
            prompt = (
                "Bạn là trợ lý phân tích dữ liệu thương mại điện tử. "
                "Luôn trả lời bằng tiếng Việt tự nhiên, ngắn gọn, dễ hiểu. "
                "Hãy mô tả bot làm được gì và đưa ra 3 ví dụ thực tế. "
                f"Câu hỏi người dùng: {question}"
            )
        elif intent == "chitchat":
            prompt = (
                "Bạn là trợ lý phân tích dữ liệu thương mại điện tử. "
                "Luôn trả lời bằng tiếng Việt trong 2-4 câu tự nhiên. "
                "Giọng điệu thân thiện, nêu ngắn gọn khả năng của bạn và gợi ý 1 câu hỏi tiếp theo. "
                f"Câu hỏi người dùng: {question}"
            )
        else:
            prompt = (
                "Bạn là trợ lý phân tích dữ liệu. "
                "Luôn trả lời bằng tiếng Việt, tóm tắt kết quả trong tối đa 4 câu. "
                f"Câu hỏi người dùng: {question}. Intent={intent}. Kết quả={result_payload}"
            )

        response = llm.invoke(prompt)
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
    graph.add_node("sql_agent", _sql_node)
    graph.add_node("retrieval_agent", _retrieval_node)
    graph.add_node("insight_agent", _insight_node)
    graph.add_node("chat_agent", _chat_node)
    graph.add_node("synthesize", _synthesize_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        _route_selector,
        {
            "sql_agent": "sql_agent",
            "retrieval_agent": "retrieval_agent",
            "insight_agent": "insight_agent",
            "chat_agent": "chat_agent",
        },
    )
    graph.add_edge("sql_agent", "synthesize")
    graph.add_edge("retrieval_agent", "synthesize")
    graph.add_edge("insight_agent", "synthesize")
    graph.add_edge("chat_agent", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


_WORKFLOW = build_graph()


def run_workflow(question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    initial_state: AgentState = {
        "question": question,
        "context": context or {},
        "warnings": [],
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
    }


def cli_run() -> None:
    parser = argparse.ArgumentParser(description="Run multi-agent workflow from terminal")
    parser.add_argument("question", type=str, help="Natural-language analytics question")
    args = parser.parse_args()

    result = run_workflow(args.question)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    cli_run()
