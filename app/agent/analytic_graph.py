"""Analytic Agent sub-graph.

Diagram:
    __start__ ─┬→ correlation
               ├→ drill_down
               └→ other
                       → __end__

Picks a branch based on question keywords. Each branch produces an `analytics` payload.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agent.analytic import (
    correlation_summary,
    drill_down_summary,
    time_series_summary,
)


class AnalyticState(TypedDict, total=False):
    rows: list[dict[str, Any]]
    question: str
    branch: str
    analytics: dict[str, Any]


_CORRELATION_HINTS = (
    "tương quan",
    "tuong quan",
    "correlation",
    "liên hệ",
    "lien he",
    "quan hệ",
    "quan he",
    "ảnh hưởng",
    "anh huong",
)
_DRILL_HINTS = (
    "drill",
    "phân tích sâu",
    "phan tich sau",
    "phân tách",
    "phan tach",
    "theo nhóm",
    "theo nhom",
    "by group",
    "top",
    "ranking",
    "xếp hạng",
    "xep hang",
)


def _branch_router(state: AnalyticState) -> str:
    q = (state.get("question") or "").lower()
    if any(k in q for k in _CORRELATION_HINTS):
        return "correlation"
    if any(k in q for k in _DRILL_HINTS):
        return "drill_down"
    return "other"


def _correlation_node(state: AnalyticState) -> AnalyticState:
    rows = state.get("rows", [])
    return {
        **state,
        "branch": "correlation",
        "analytics": {"correlation": correlation_summary(rows)},
    }


def _drill_down_node(state: AnalyticState) -> AnalyticState:
    rows = state.get("rows", [])
    return {
        **state,
        "branch": "drill_down",
        "analytics": {"drill_down": drill_down_summary(rows)},
    }


def _other_node(state: AnalyticState) -> AnalyticState:
    """Default branch — produce all summaries so synthesize has rich context."""
    rows = state.get("rows", [])
    return {
        **state,
        "branch": "other",
        "analytics": {
            "drill_down": drill_down_summary(rows),
            "correlation": correlation_summary(rows),
            "time_series": time_series_summary(rows),
        },
    }


def build_analytic_graph() -> Any:
    graph = StateGraph(AnalyticState)
    graph.add_node("correlation", _correlation_node)
    graph.add_node("drill_down", _drill_down_node)
    graph.add_node("other", _other_node)

    graph.add_conditional_edges(
        START,
        _branch_router,
        {"correlation": "correlation", "drill_down": "drill_down", "other": "other"},
    )
    for branch in ("correlation", "drill_down", "other"):
        graph.add_edge(branch, END)

    return graph.compile()


_GRAPH = build_analytic_graph()


def run_analytic_graph(rows: list[dict[str, Any]], question: str) -> dict[str, Any]:
    initial: AnalyticState = {"rows": rows, "question": question}
    final = _GRAPH.invoke(initial)
    return {
        "branch": final.get("branch", "other"),
        "analytics": final.get("analytics", {}),
    }
