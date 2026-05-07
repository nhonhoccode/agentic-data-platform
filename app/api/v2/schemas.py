from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class RuleConfig(BaseModel):
    allow_agent: bool = True
    allow_kpi: bool = True
    allow_sql: bool = True
    allow_schema: bool = True
    allow_definition: bool = True
    sql_limit: int = Field(default=500, ge=1, le=5000)


class HistoryTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    rules: RuleConfig = Field(default_factory=RuleConfig)
    history: list[HistoryTurn] = Field(default_factory=list)


class TracePayload(BaseModel):
    inferred_intent: str
    selected_tools: list[str] = Field(default_factory=list)
    sql: str | None = None
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    blocked: bool = False


class Block(BaseModel):
    type: Literal["text", "table", "figure", "warnings"]
    title: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    mode: str
    assistant_message: str
    active_rules: RuleConfig
    blocks: list[Block] = Field(default_factory=list)
    trace: TracePayload


class QueryRequest(BaseModel):
    sql: str = Field(..., min_length=1)
    limit: int = Field(default=500, ge=1, le=5000)


class QueryResponse(BaseModel):
    executed_sql: str
    row_count: int
    columns: list[str]
    rows: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    assistant_name: str
    description: str
    can_do: list[str]
    quick_commands: list[dict[str, str]]
    slash_commands: dict[str, str]
    rule_targets: list[str]
    guardrails: list[str]


class DashboardRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    top_categories_limit: int = Field(default=8, ge=1, le=20)


class DashboardResponse(BaseModel):
    context: dict[str, str | None]
    overview: dict[str, Any]
    series: list[dict[str, Any]]
    series_row_count: int
    top_categories: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
