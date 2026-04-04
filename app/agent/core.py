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
            "I can help with KPI summary, schema search, business definitions, "
            "and read-only SQL analytics. Try /help in UI for examples."
        )
    if intent == "chitchat":
        return (
            "Hi. Ask naturally about KPI, revenue trends, schema, or business terms, "
            "and I will route to the right tool."
        )
    if intent == "schema_search":
        return f"Found {result.get('match_count', 0)} schema matches for your keyword."
    if intent == "business_definition":
        if result.get("found"):
            definition = result["definition"]
            return f"{definition['term']}: {definition['definition']}"
        return "Definition not found. Please use one of the available terms."
    if intent == "kpi_summary":
        overview = result.get("overview", {})
        return (
            "KPI summary loaded: "
            f"orders={overview.get('total_orders')}, gmv={overview.get('gmv')}, "
            f"delivered_rate={overview.get('delivered_order_rate')}"
        )

    rows = result.get("row_count", 0)
    return f"Query executed successfully with {rows} rows returned."


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

        model_kwargs: dict[str, Any] = {}
        if not settings.llm_enable_thinking:
            model_kwargs = {
                "extra_body": {
                    "chat_template_kwargs": {
                        "enable_thinking": False,
                    }
                }
            }

        return ChatOpenAI(
            model=settings.model_api_base,
            api_key=settings.openai_api_key,
            base_url=settings.base_url,
            temperature=settings.temperature,
            model_kwargs=model_kwargs or None,
        )

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
        if state.get("intent") in {"help_request", "chitchat"}:
            return None

        llm = _build_summarization_llm()
        if llm is None:
            return None

        prompt = (
            "You are an analytics assistant. Summarize the result in <=4 sentences. "
            f"Intent={state['intent']}. Result={json.dumps(state.get('raw_result', {}), default=str)[:5000]}"
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
        "result_summary": result.get("result_summary", "No summary generated."),
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
