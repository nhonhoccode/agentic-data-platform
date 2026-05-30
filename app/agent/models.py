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
    web_search: dict[str, Any] | None
    pending_agents: list[str]
    completed_agents: list[str]
    iteration: int
    history: list[HistoryTurn]  # prior turns from frontend
    # Web-search toggle + canned-refusal short-circuit propagation
    # (declared here so LangGraph keeps them between nodes).
    web_search_enabled: bool
    force_web_search: bool
    blocked_answer: str
    blocked_reason: str


def assert_state_keys(state: dict[str, Any], where: str = "") -> None:
    """Dev-only sanity check: warn when a node tries to set a key that isn't
    in AgentState's TypedDict. LangGraph silently drops unknown keys, so this
    catches the kind of drift that caused the 'blocked_answer never propagates'
    bug earlier.

    Cheap; safe to leave on in dev. Skip in prod by checking APP_ENV.
    """
    import os

    if os.environ.get("APP_ENV", "dev").lower() in {"prod", "production"}:
        return
    allowed = set(AgentState.__annotations__.keys())
    unknown = [k for k in state.keys() if k not in allowed and not k.startswith("_")]
    if unknown:
        import logging

        logging.getLogger(__name__).warning(
            "AgentState drift in %s — unknown keys will be stripped by LangGraph: %s",
            where or "?",
            unknown,
        )
