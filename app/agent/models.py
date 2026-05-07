from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class HistoryTurn(TypedDict, total=False):
    role: str  # "user" | "assistant"
    content: str
    intent: str
    sql: str | None


class AgentState(TypedDict, total=False):
    question: str
    context: dict[str, Any]
    intent: str
    route: str
    selected_tools: list[str]
    sql: str | None
    raw_result: dict[str, Any]
    result_summary: str
    confidence: float
    warnings: list[str]
    chart: dict[str, Any] | None
    analytics: dict[str, Any] | None
    pending_agents: list[str]
    completed_agents: list[str]
    iteration: int
    history: list[HistoryTurn]  # prior turns from frontend
