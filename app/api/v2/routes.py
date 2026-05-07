from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agent.core import stream_workflow
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


def _sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = run_chat(payload)
        return ChatResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest) -> StreamingResponse:
    history = [h.model_dump() for h in payload.history]

    async def event_generator():
        try:
            async for event in stream_workflow(
                payload.message, payload.context, history=history
            ):
                yield _sse(event["type"], event)
        except UnsafeQueryError as exc:
            yield _sse("error", {"detail": str(exc)})
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
