from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class QueryDataRequest(BaseModel):
    sql: str = Field(..., description="Read-only SQL query")
    limit: int = Field(default=500, ge=1, le=5000)


class QueryDataResponse(BaseModel):
    executed_sql: str
    row_count: int
    data: list[dict[str, Any]]
    warnings: list[str]


class SearchSchemaRequest(BaseModel):
    keyword: str = Field(..., min_length=1)
    schemas: list[str] = Field(default_factory=lambda: ["raw", "staging", "marts", "serving"])


class SearchSchemaResponse(BaseModel):
    keyword: str
    match_count: int
    matches: list[dict[str, Any]]


class BusinessDefinitionResponse(BaseModel):
    found: bool
    definition: dict[str, Any] | None
    available_terms: list[str] | None = None


class KpiSummaryRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None


class KpiSummaryResponse(BaseModel):
    overview: dict[str, Any]
    series: list[dict[str, Any]]
    series_row_count: int


class AgentWorkflowRequest(BaseModel):
    question: str = Field(..., min_length=3)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowResponse(BaseModel):
    intent: str
    selected_tools: list[str]
    sql: str | None
    result_summary: str
    confidence: float
    warnings: list[str]
    raw_result: dict[str, Any]
