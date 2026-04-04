from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


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
