from fastapi import APIRouter, Depends, HTTPException

from app.agent.core import run_workflow
from app.api.deps import require_api_key
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
from app.db.sql_safety import UnsafeQueryError
from app.services.query_service import QueryService

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
service = QueryService()


@router.post("/query_data", response_model=QueryDataResponse)
def query_data(payload: QueryDataRequest) -> QueryDataResponse:
    try:
        result = service.query_data(payload.sql, limit=payload.limit)
        return QueryDataResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search_schema", response_model=SearchSchemaResponse)
def search_schema(payload: SearchSchemaRequest) -> SearchSchemaResponse:
    result = service.search_schema(payload.keyword, schemas=payload.schemas)
    return SearchSchemaResponse(**result)


@router.get("/get_business_definition", response_model=BusinessDefinitionResponse)
def get_business_definition(term: str) -> BusinessDefinitionResponse:
    result = service.get_business_definition(term)
    return BusinessDefinitionResponse(**result)


@router.post("/get_kpi_summary", response_model=KpiSummaryResponse)
def get_kpi_summary(payload: KpiSummaryRequest) -> KpiSummaryResponse:
    result = service.get_kpi_summary(start_date=payload.start_date, end_date=payload.end_date)
    return KpiSummaryResponse(**result)


@router.post("/run_agent_workflow", response_model=AgentWorkflowResponse)
def run_agent_workflow(payload: AgentWorkflowRequest) -> AgentWorkflowResponse:
    result = run_workflow(payload.question, payload.context)
    return AgentWorkflowResponse(**result)
