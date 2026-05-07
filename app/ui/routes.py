from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from app.agent.core import stream_workflow
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
from app.ui.capabilities import UI_CAPABILITIES
from app.ui.upload import handle_upload

router = APIRouter(prefix="/ui", tags=["ui"])

DATA_NOT_READY_HINT = (
    "Data platform may not be initialized yet. "
    "Check bootstrap logs with: docker compose logs -f bootstrap"
)

_DIST_INDEX = Path(__file__).resolve().parent / "static" / "dist" / "index.html"


def _service_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{DATA_NOT_READY_HINT}. Error: {exc}")


@router.get("", response_class=HTMLResponse)
def ui_home() -> str:
    if _DIST_INDEX.exists():
        return _DIST_INDEX.read_text(encoding="utf-8")
    return "<h1>Frontend not built. Run: cd frontend && npm install && npm run build</h1>"


def _sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


@router.post("/proxy/chat/stream")
async def proxy_chat_stream(payload: ChatRequest) -> StreamingResponse:
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


@router.post("/proxy/upload")
async def proxy_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        return await handle_upload(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


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
