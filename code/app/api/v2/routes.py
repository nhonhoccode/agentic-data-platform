from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_api_key
from app.api.v2.schemas import (
    CapabilitiesResponse,
    ChatRequest,
    ChatResponse,
    QueryRequest,
    QueryResponse,
)
from app.api.v2.service import run_chat, run_query
from app.db.sql_safety import UnsafeQueryError
from app.ui.capabilities import UI_CAPABILITIES

router = APIRouter(prefix="/api/v2", dependencies=[Depends(require_api_key)], tags=["api-v2"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = run_chat(payload)
        return ChatResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    try:
        result = run_query(payload.sql, payload.limit)
        return QueryResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/capabilities", response_model=CapabilitiesResponse)
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(**UI_CAPABILITIES)
