from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-IP limiter shared across UI routes. Mounted via SlowAPIMiddleware in main.
limiter = Limiter(key_func=get_remote_address)

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
from app.ui.auth import check_credentials, issue_token, verify_token
from app.ui.capabilities import UI_CAPABILITIES
from app.ui.chatstore import (
    append_message,
    create_conversation,
    delete_conversation,
    export_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    rename_conversation,
    search_conversations,
)
from app.ui.upload import handle_upload
from app.ui.userstore import (
    UserStoreError,
    create_user,
    get_user_info,
    has_feature,
    is_admin as _is_admin_user,
    list_users,
    set_is_admin,
    set_tier,
    user_count,
    user_exists,
    verify_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["ui"])

DATA_NOT_READY_HINT = (
    "Data platform may not be initialized yet. "
    "Check bootstrap logs with: docker compose logs -f bootstrap"
)

_DIST_INDEX = Path(__file__).resolve().parent / "static" / "dist" / "index.html"


def _service_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"{DATA_NOT_READY_HINT}. Error: {exc}")


def require_session(request: Request) -> str:
    """FastAPI dependency: extract + verify the UI session token. Returns username."""
    auth = request.headers.get("authorization", "")
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.cookies.get("ui_session") or ""
    claims = verify_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="missing_or_invalid_session")
    return claims.username


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    token: str
    username: str
    expires_in: int
    tier: str = "basic"
    is_admin: bool = False
    features: list[str] = Field(default_factory=list)


class MeResponse(BaseModel):
    username: str
    tier: str = "basic"
    is_admin: bool = False
    features: list[str] = Field(default_factory=list)


class TierUpdateRequest(BaseModel):
    tier: str = Field(..., pattern="^(basic|approved|admin)$")


class AdminUpdateRequest(BaseModel):
    is_admin: bool


def _user_payload(username: str) -> dict[str, Any]:
    from app.ui.userstore import _TIER_FEATURES, get_user_info

    info = get_user_info(username) or {
        "username": username,
        "tier": "basic",
        "is_admin": False,
    }
    features = sorted(_TIER_FEATURES.get(info.get("tier") or "basic", set()))
    return {
        "username": info.get("username", username),
        "tier": info.get("tier", "basic"),
        "is_admin": bool(info.get("is_admin", False)),
        "features": features,
    }


@router.get("", response_class=HTMLResponse)
def ui_home() -> str:
    if _DIST_INDEX.exists():
        return _DIST_INDEX.read_text(encoding="utf-8")
    return "<h1>Frontend not built. Run: cd frontend && npm install && npm run build</h1>"


@router.post("/proxy/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def proxy_auth_login(request: Request, payload: LoginRequest) -> LoginResponse:
    # Admin from env first (always works on fresh installs), then SQLite users.
    ok = check_credentials(payload.username, payload.password) or verify_user(
        payload.username, payload.password
    )
    if not ok:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    from app.config import get_settings

    settings = get_settings()
    token = issue_token(payload.username)
    info = _user_payload(payload.username)
    return LoginResponse(
        token=token,
        expires_in=settings.app_session_ttl_sec,
        **info,
    )


@router.post("/proxy/auth/register", response_model=LoginResponse)
@limiter.limit("5/minute")
def proxy_auth_register(request: Request, payload: LoginRequest) -> LoginResponse:
    from app.config import get_settings

    settings = get_settings()
    if payload.username.strip().lower() == settings.app_admin_username.lower():
        raise HTTPException(status_code=400, detail="username_reserved")
    if user_exists(payload.username):
        raise HTTPException(status_code=409, detail="username_taken")
    try:
        create_user(payload.username, payload.password)
    except UserStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = issue_token(payload.username)
    info = _user_payload(payload.username)
    return LoginResponse(
        token=token,
        expires_in=settings.app_session_ttl_sec,
        **info,
    )


@router.get("/proxy/auth/me", response_model=MeResponse)
def proxy_auth_me(username: str = Depends(require_session)) -> MeResponse:
    return MeResponse(**_user_payload(username))


def require_admin(username: str = Depends(require_session)) -> str:
    """FastAPI dep: gate endpoints that only admins (is_admin or tier=admin) may use."""
    if not _is_admin_user(username):
        raise HTTPException(status_code=403, detail="admin_required")
    return username


def require_feature(feature: str):
    """Dep factory. Use as: Depends(require_feature("web_search"))."""

    def _dep(username: str = Depends(require_session)) -> str:
        if not has_feature(username, feature):
            raise HTTPException(
                status_code=403,
                detail=f"feature_not_allowed:{feature}",
            )
        return username

    return _dep


# ---------------------------------------------------------------------------
# Admin endpoints — list users, change tier, toggle is_admin.
# ---------------------------------------------------------------------------


@router.get("/proxy/admin/users")
def proxy_admin_users(_admin: str = Depends(require_admin)) -> dict[str, Any]:
    return {"users": list_users()}


@router.patch("/proxy/admin/users/{target_username}/tier")
def proxy_admin_set_tier(
    target_username: str,
    payload: TierUpdateRequest,
    admin: str = Depends(require_admin),
) -> dict[str, Any]:
    from app.config import get_settings

    if target_username == get_settings().app_admin_username:
        raise HTTPException(status_code=400, detail="cannot_modify_env_admin")
    try:
        ok = set_tier(target_username, payload.tier)
    except UserStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="user_not_found")
    return {"user": _user_payload(target_username)}


@router.patch("/proxy/admin/users/{target_username}/admin")
def proxy_admin_set_admin(
    target_username: str,
    payload: AdminUpdateRequest,
    admin: str = Depends(require_admin),
) -> dict[str, Any]:
    from app.config import get_settings

    env_admin = get_settings().app_admin_username
    if target_username == env_admin:
        raise HTTPException(status_code=400, detail="cannot_modify_env_admin")
    if not set_is_admin(target_username, bool(payload.is_admin)):
        raise HTTPException(status_code=404, detail="user_not_found")
    return {"user": _user_payload(target_username)}


@router.get("/proxy/auth/stats")
def proxy_auth_stats() -> dict[str, int]:
    return {"registered_users": user_count()}


def _sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


def _auto_title(first_user_message: str) -> str:
    """Generate a 1-line title from the first user message (cheap, no LLM)."""
    text = (first_user_message or "").strip()
    if not text:
        return "New chat"
    text = text.splitlines()[0].strip()
    if len(text) > 60:
        text = text[:57].rstrip() + "..."
    return text or "New chat"


def _resolve_conversation(username: str, conversation_id: str | None) -> str:
    """Return a valid, user-owned conversation id, creating one if missing."""
    if conversation_id:
        existing = get_conversation(username, conversation_id)
        if existing is not None:
            return conversation_id
    return create_conversation(username, "New chat")


@router.post("/proxy/chat/stream")
@limiter.limit("60/minute")
async def proxy_chat_stream(
    request: Request,
    payload: ChatRequest,
    user: str = Depends(require_session),
) -> StreamingResponse:
    # If the user lacks web_search permission, silently downgrade the flags so
    # the agent treats it as a normal "toggle off" — the resulting canned text
    # explains the situation. This avoids a 403 mid-conversation.
    if (payload.web_search_enabled or payload.force_web_search) and not has_feature(
        user, "web_search"
    ):
        payload = payload.model_copy(
            update={"web_search_enabled": False, "force_web_search": False}
        )

    # Resolve / create conversation up-front (sync). DB is source of truth
    # for history — we override any client-supplied history below.
    conv_id = _resolve_conversation(user, payload.conversation_id)
    conv_meta = get_conversation(user, conv_id) or {"id": conv_id, "title": "New chat"}

    # Persist the user's message first so it survives mid-stream disconnects.
    try:
        append_message(conv_id, user, "user", payload.message, None)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="conversation_forbidden") from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("append_user_message_failed: %s", exc)

    # Backend-trusted history (drops blocked refusal turns inside core's rewriter).
    stored_history = list_messages(conv_id, user, limit=24)
    history = [
        {
            "role": m.get("role"),
            "content": m.get("content"),
            "metadata": (m.get("payload") or {}) if isinstance(m.get("payload"), dict) else None,
        }
        for m in stored_history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    # Don't mutate payload.history — use model_copy.
    request_payload = payload.model_copy(update={"history": history, "conversation_id": conv_id})

    async def event_generator():
        delta: dict[str, Any] | None = None
        accumulated_text = ""
        try:
            # First, announce the active conversation so the UI can update.
            yield _sse(
                "conversation",
                {
                    "id": conv_id,
                    "title": conv_meta.get("title", "New chat"),
                },
            )

            async for event in stream_workflow(
                request_payload.message,
                request_payload.context,
                history=history,
                web_search_enabled=bool(request_payload.web_search_enabled),
                force_web_search=bool(getattr(request_payload, "force_web_search", False)),
            ):
                etype = event.get("type")
                if etype == "token":
                    text = event.get("text") or ""
                    if not isinstance(text, str):
                        text = str(text)
                    accumulated_text += text
                elif etype == "final":
                    delta = dict(event)
                yield _sse(etype or "event", event)
        except UnsafeQueryError as exc:
            yield _sse("error", {"detail": str(exc)})
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"detail": str(exc)})
        finally:
            # Persist assistant message + auto-title.
            try:
                final_text = accumulated_text.strip()
                if not final_text and isinstance(delta, dict):
                    final_text = str(delta.get("result_summary") or "").strip()
                if not final_text:
                    final_text = "(không tạo được câu trả lời)"
                ws = (delta or {}).get("web_search") if isinstance(delta, dict) else None
                ws_payload = ws if isinstance(ws, dict) else None
                blocked_reason = (delta or {}).get("blocked_reason") if isinstance(delta, dict) else None
                payload_to_store: dict[str, Any] = {
                    "intent": (delta or {}).get("intent") if isinstance(delta, dict) else None,
                    "sql": (delta or {}).get("sql") if isinstance(delta, dict) else None,
                    "web_search": ws_payload,
                    "chart": (delta or {}).get("chart") if isinstance(delta, dict) else None,
                    "analytics": (delta or {}).get("analytics") if isinstance(delta, dict) else None,
                    "tool_calls": (delta or {}).get("selected_tools") if isinstance(delta, dict) else None,
                    "warnings": (delta or {}).get("warnings") if isinstance(delta, dict) else None,
                    "result_summary": final_text,
                    "confidence": (delta or {}).get("confidence") if isinstance(delta, dict) else None,
                    "blocked_reason": blocked_reason,
                    "blocked": bool(blocked_reason),
                }
                try:
                    append_message(conv_id, user, "assistant", final_text, payload_to_store)
                except PermissionError:
                    logger.warning("append_assistant_message_forbidden conv=%s user=%s", conv_id, user)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("append_assistant_message_failed: %s", exc)

                # Auto-title: only when still 'New chat' / ''.
                try:
                    rename_conversation(
                        user, conv_id, _auto_title(payload.message), only_if_default=True
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("auto_title_failed: %s", exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("stream_finalize_failed: %s", exc)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Conversation management endpoints
# ---------------------------------------------------------------------------


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


@router.post("/proxy/conversations")
@limiter.limit("30/minute")
def proxy_conversations_create(
    request: Request,
    payload: ConversationCreateRequest | None = None,
    user: str = Depends(require_session),
) -> dict[str, Any]:
    title = (payload.title if payload else None) or "New chat"
    conv_id = create_conversation(user, title)
    meta = get_conversation(user, conv_id) or {"id": conv_id, "title": title}
    return {"id": conv_id, "title": meta.get("title", title), "created_at": meta.get("created_at")}


@router.get("/proxy/conversations")
def proxy_conversations_list(user: str = Depends(require_session)) -> dict[str, Any]:
    return {"conversations": list_conversations(user)}


@router.get("/proxy/conversations/{conversation_id}")
def proxy_conversations_get(
    conversation_id: str, user: str = Depends(require_session)
) -> dict[str, Any]:
    meta = get_conversation(user, conversation_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    msgs = list_messages(conversation_id, user, limit=200)
    return {"conversation": meta, "messages": msgs}


@router.patch("/proxy/conversations/{conversation_id}")
def proxy_conversations_rename(
    conversation_id: str,
    payload: ConversationRenameRequest,
    user: str = Depends(require_session),
) -> dict[str, Any]:
    ok = rename_conversation(user, conversation_id, payload.title, only_if_default=False)
    if not ok:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    meta = get_conversation(user, conversation_id)
    return {"conversation": meta}


@router.delete("/proxy/conversations/{conversation_id}")
def proxy_conversations_delete(
    conversation_id: str, user: str = Depends(require_session)
) -> dict[str, Any]:
    ok = delete_conversation(user, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return {"deleted": True, "id": conversation_id}


@router.get("/proxy/conversations/search/q")
def proxy_conversations_search(
    q: str = "",
    limit: int = 30,
    user: str = Depends(require_session),
) -> dict[str, Any]:
    q = (q or "").strip()
    if not q:
        return {"query": "", "results": []}
    results = search_conversations(user, q, limit=limit)
    return {"query": q, "results": results}


@router.get("/proxy/conversations/{conversation_id}/export")
def proxy_conversations_export(
    conversation_id: str, user: str = Depends(require_feature("export"))
) -> dict[str, Any]:
    bundle = export_conversation(user, conversation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return bundle


@router.post("/proxy/upload")
async def proxy_upload(
    file: UploadFile = File(...),
    _user: str = Depends(require_feature("upload")),
) -> dict[str, Any]:
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
def proxy_chat(
    payload: ChatRequest, user: str = Depends(require_session)
) -> ChatResponse:
    try:
        # Same silent downgrade as the streaming path.
        if (payload.web_search_enabled or payload.force_web_search) and not has_feature(
            user, "web_search"
        ):
            payload = payload.model_copy(
                update={"web_search_enabled": False, "force_web_search": False}
            )
        conv_id = _resolve_conversation(user, payload.conversation_id)

        # Persist user message; then override history from DB (source of truth).
        try:
            append_message(conv_id, user, "user", payload.message, None)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="conversation_forbidden") from exc
        except Exception as exc:  # noqa: BLE001
            logger.warning("append_user_message_failed_sync: %s", exc)

        stored = list_messages(conv_id, user, limit=24)
        history = [
            {
                "role": m.get("role"),
                "content": m.get("content"),
                "metadata": (m.get("payload") or {}) if isinstance(m.get("payload"), dict) else None,
            }
            for m in stored
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        # Don't mutate payload.history — model_copy.
        request_payload = payload.model_copy(
            update={"history": history, "conversation_id": conv_id}
        )

        result = run_chat(request_payload)

        # Persist assistant response + auto-title.
        try:
            assistant_text = str(result.get("assistant_message") or "").strip() or "(không tạo được câu trả lời)"
            trace = result.get("trace") or {}
            trace_dict = trace.model_dump() if hasattr(trace, "model_dump") else (trace if isinstance(trace, dict) else {})
            append_message(
                conv_id,
                user,
                "assistant",
                assistant_text,
                {
                    "intent": trace_dict.get("inferred_intent"),
                    "sql": trace_dict.get("sql"),
                    "warnings": trace_dict.get("warnings"),
                    "blocked": bool(trace_dict.get("blocked")),
                    "result_summary": assistant_text,
                    "mode": result.get("mode"),
                },
            )
            rename_conversation(
                user, conv_id, _auto_title(payload.message), only_if_default=True
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("sync_chat_persist_failed: %s", exc)

        return ChatResponse(**result)
    except HTTPException:
        raise
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/query", response_model=QueryResponse)
def proxy_query(
    payload: QueryRequest, _user: str = Depends(require_session)
) -> QueryResponse:
    try:
        result = run_query(payload.sql, payload.limit)
        return QueryResponse(**result)
    except UnsafeQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc


@router.post("/proxy/dashboard", response_model=DashboardResponse)
def proxy_dashboard(
    payload: DashboardRequest, _user: str = Depends(require_session)
) -> DashboardResponse:
    try:
        result = get_dashboard(
            start_date=payload.start_date,
            end_date=payload.end_date,
            top_categories_limit=payload.top_categories_limit,
        )
        return DashboardResponse(**result)
    except Exception as exc:  # noqa: BLE001
        raise _service_unavailable(exc) from exc
