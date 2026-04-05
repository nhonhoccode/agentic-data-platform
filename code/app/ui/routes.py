from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.agent.core import run_workflow
from app.api.schemas import (
    AgentWorkflowRequest,
    AgentWorkflowResponse,
    BusinessDefinitionResponse,
    KpiSummaryRequest,
    KpiSummaryResponse,
    QueryDataRequest,
    QueryDataResponse,
    SearchSchemaRequest,
    SearchSchemaResponse,
)
from app.api.v2.schemas import (
    CapabilitiesResponse,
    ChatRequest,
    ChatResponse,
    DashboardRequest,
    DashboardResponse,
    QueryRequest,
    QueryResponse,
)
from app.api.v2.service import get_dashboard, run_chat, run_query
from app.db.sql_safety import UnsafeQueryError
from app.services.query_service import QueryService
from app.ui.capabilities import UI_CAPABILITIES

router = APIRouter(prefix="/ui", tags=["ui"])
service = QueryService()

DATA_NOT_READY_HINT = (
    "Data platform may not be initialized yet. "
    "Check bootstrap logs with: docker compose logs -f bootstrap"
)

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "index.html"


def _service_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{DATA_NOT_READY_HINT}. Error: {exc}")


@router.get("", response_class=HTMLResponse)
def ui_home() -> str:
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return html


@router.get("/proxy/capabilities", response_model=CapabilitiesResponse)
def proxy_capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(**UI_CAPABILITIES)


@router.post("/proxy/chat", response_model=ChatResponse)
def proxy_chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = run_chat(payload)
        return ChatResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/query", response_model=QueryResponse)
def proxy_query(payload: QueryRequest) -> QueryResponse:
    try:
        result = run_query(payload.sql, payload.limit)
        return QueryResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/dashboard", response_model=DashboardResponse)
def proxy_dashboard(payload: DashboardRequest) -> DashboardResponse:
    try:
        result = get_dashboard(
            start_date=payload.start_date,
            end_date=payload.end_date,
            top_categories_limit=payload.top_categories_limit,
        )
        return DashboardResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


# --- Backward-compatible v1 proxy wrappers (kept short-term) ---


@router.post("/proxy/kpi", response_model=KpiSummaryResponse)
def proxy_kpi(payload: KpiSummaryRequest) -> KpiSummaryResponse:
    try:
        result = service.get_kpi_summary(start_date=payload.start_date, end_date=payload.end_date)
        return KpiSummaryResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/agent", response_model=AgentWorkflowResponse)
def proxy_agent(payload: AgentWorkflowRequest) -> AgentWorkflowResponse:
    try:
        result = run_workflow(payload.question, payload.context)
        return AgentWorkflowResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/sql", response_model=QueryDataResponse)
def proxy_sql(payload: QueryDataRequest) -> QueryDataResponse:
    try:
        result = service.query_data(payload.sql, limit=payload.limit)
        return QueryDataResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/schema", response_model=SearchSchemaResponse)
def proxy_schema(payload: SearchSchemaRequest) -> SearchSchemaResponse:
    try:
        result = service.search_schema(payload.keyword, schemas=payload.schemas)
        return SearchSchemaResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.get("/proxy/definition", response_model=BusinessDefinitionResponse)
def proxy_definition(term: str) -> BusinessDefinitionResponse:
    try:
        result = service.get_business_definition(term)
        return BusinessDefinitionResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.get("/proxy/deprecations")
def proxy_deprecations() -> dict[str, Any]:
    return {
        "message": "UI proxy v1 wrappers are deprecated. Please migrate to /api/v2/* or /ui/proxy/chat + /ui/proxy/query.",
        "deprecated_routes": [
            "/ui/proxy/kpi",
            "/ui/proxy/agent",
            "/ui/proxy/sql",
            "/ui/proxy/schema",
            "/ui/proxy/definition",
        ],
    }
