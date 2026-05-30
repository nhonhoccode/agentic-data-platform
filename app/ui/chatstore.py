"""SQLite-backed chat conversation store.

Mirrors the `userstore.py` pattern: WAL journaling, per-call _connect(),
threading.RLock() guard, schema migration via PRAGMA user_version.

All ownership-sensitive functions take `username` first (after the
positional id) and enforce ownership inside the same transaction via
JOIN — protecting against IDOR enumeration of other users'
conversations / messages.

Persists to ``<data_dir>/chat.db`` (sibling of auth.db, also in the
Docker bind-mount so chats survive container recreates).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()

_SCHEMA_VERSION = 1


def _db_path() -> Path:
    settings = get_settings()
    base = Path(settings.data_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base / "chat.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now_ts() -> int:
    return int(time.time())


def init_db() -> None:
    """Create the tables if not present; bump user_version when migrating."""
    with _lock:
        conn = _connect()
        try:
            current = conn.execute("PRAGMA user_version").fetchone()
            current_version = int(current[0]) if current else 0

            if current_version < 1:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        username TEXT NOT NULL,
                        title TEXT,
                        created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        username TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        payload_json TEXT,
                        sequence_no INTEGER NOT NULL,
                        created_at INTEGER NOT NULL,
                        UNIQUE(conversation_id, sequence_no),
                        FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_conv_user_updated "
                    "ON conversations(username, updated_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_msg_conv_seq "
                    "ON messages(conversation_id, sequence_no)"
                )
                conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Payload sanitization — keep stored JSON small + safe against malformed data
# ---------------------------------------------------------------------------
_PAYLOAD_BYTE_LIMIT = 100 * 1024
_MAX_LIST_ITEMS = 50


def _cap_payload(payload: Any) -> dict[str, Any]:
    """Trim long lists, drop non-dict items, ensure JSON-safety.

    Always uses isinstance() guards before .get / dict spread to avoid
    TypeError on malformed inputs (e.g. tool_calls accidentally being a
    string). Returns a dict ready for json.dumps.
    """
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return {"_raw": str(payload)[:1000]}

    out: dict[str, Any] = {}
    for k, v in payload.items():
        out[k] = v

    # raw_result.data truncation
    raw_result = out.get("raw_result")
    if isinstance(raw_result, dict):
        capped_raw = dict(raw_result)
        data = capped_raw.get("data")
        if isinstance(data, list) and len(data) > _MAX_LIST_ITEMS:
            capped_raw["data"] = data[:_MAX_LIST_ITEMS]
            capped_raw["_data_truncated_from"] = len(data)
        out["raw_result"] = capped_raw

    # tool_calls — only keep dict items + cap each detail field to 500 chars
    tool_calls = out.get("tool_calls")
    if isinstance(tool_calls, list):
        capped_calls: list[dict[str, Any]] = []
        for c in tool_calls[:_MAX_LIST_ITEMS]:
            if not isinstance(c, dict):
                continue
            row = dict(c)
            detail = row.get("detail")
            if isinstance(detail, str) and len(detail) > 500:
                row["detail"] = detail[:499] + "…"
            label = row.get("label")
            if isinstance(label, str) and len(label) > 200:
                row["label"] = label[:199] + "…"
            capped_calls.append(row)
        out["tool_calls"] = capped_calls

    # web_search.results — only keep dict items
    web_search = out.get("web_search")
    if isinstance(web_search, dict):
        capped_ws = dict(web_search)
        results = capped_ws.get("results")
        if isinstance(results, list):
            capped_ws["results"] = [r for r in results if isinstance(r, dict)][:_MAX_LIST_ITEMS]
        out["web_search"] = capped_ws

    # Size guard — if still too big, drop heavy fields.
    try:
        serialized = json.dumps(out, default=str)
    except (TypeError, ValueError):
        return {"_truncated": True, "intent": out.get("intent"), "sql": out.get("sql"),
                "result_summary": out.get("result_summary")}
    if len(serialized.encode("utf-8")) > _PAYLOAD_BYTE_LIMIT:
        return {
            "_truncated": True,
            "intent": out.get("intent"),
            "sql": out.get("sql"),
            "result_summary": out.get("result_summary"),
        }
    return out


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------


def create_conversation(username: str, title: str | None = None) -> str:
    """Create a new conversation owned by `username`. Returns its UUID."""
    if not username:
        raise ValueError("username_required")
    init_db()
    conv_id = uuid.uuid4().hex
    now = _now_ts()
    safe_title = (title or "New chat").strip()[:200] or "New chat"
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO conversations (id, username, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (conv_id, username, safe_title, now, now),
            )
        finally:
            conn.close()
    return conv_id


def list_conversations(username: str) -> list[dict[str, Any]]:
    """Return user's conversations newest-first with message counts."""
    if not username:
        return []
    init_db()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.updated_at,
                       (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
                FROM conversations c
                WHERE c.username = ?
                ORDER BY c.updated_at DESC
                """,
                (username,),
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "id": r[0],
            "title": r[1] or "New chat",
            "updated_at": int(r[2]) if r[2] is not None else 0,
            "message_count": int(r[3] or 0),
        }
        for r in rows
    ]


def get_conversation(username: str, conversation_id: str) -> dict[str, Any] | None:
    """Return conversation metadata if owned by `username`, else None."""
    if not username or not conversation_id:
        return None
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "WHERE id = ? AND username = ?",
                (conversation_id, username),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "title": row[1] or "New chat",
        "created_at": int(row[2]) if row[2] is not None else 0,
        "updated_at": int(row[3]) if row[3] is not None else 0,
    }


def delete_conversation(username: str, conversation_id: str) -> bool:
    """Delete conversation + messages cascade. Returns True if a row was removed."""
    if not username or not conversation_id:
        return False
    init_db()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "DELETE FROM conversations WHERE id = ? AND username = ?",
                (conversation_id, username),
            )
            return (cur.rowcount or 0) > 0
        finally:
            conn.close()


def rename_conversation(
    username: str,
    conversation_id: str,
    title: str,
    only_if_default: bool = False,
) -> bool:
    """Rename a conversation. When `only_if_default` is True, only updates
    titles still equal to 'New chat' / '' — used for the auto-title
    background pass so we never overwrite an explicit user rename."""
    if not username or not conversation_id:
        return False
    safe_title = (title or "").strip()[:200]
    if not safe_title:
        return False
    init_db()
    now = _now_ts()
    with _lock:
        conn = _connect()
        try:
            if only_if_default:
                cur = conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? "
                    "WHERE id = ? AND username = ? AND (title IS NULL OR title IN ('New chat', ''))",
                    (safe_title, now, conversation_id, username),
                )
            else:
                cur = conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? "
                    "WHERE id = ? AND username = ?",
                    (safe_title, now, conversation_id, username),
                )
            return (cur.rowcount or 0) > 0
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Message CRUD
# ---------------------------------------------------------------------------


def append_message(
    conversation_id: str,
    username: str,
    role: str,
    content: str,
    payload: Any = None,
) -> str:
    """Insert a message into `conversation_id`. Verifies ownership inside
    the same transaction via JOIN. Atomically assigns sequence_no =
    MAX+1; retries up to 3 times on UNIQUE / OperationalError races.

    Raises PermissionError if `username` does not own the conversation.
    """
    if not conversation_id or not username:
        raise ValueError("conversation_id_and_username_required")

    init_db()
    payload_text: str
    try:
        payload_text = json.dumps(_cap_payload(payload), default=str, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        logger.warning("payload_serialize_failed: %s", exc)
        payload_text = json.dumps({"_serialize_error": str(exc)})

    msg_id = uuid.uuid4().hex
    now = _now_ts()
    role_safe = (role or "user")[:32]
    last_exc: Exception | None = None

    for attempt in range(3):
        with _lock:
            conn = _connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                owner_row = conn.execute(
                    "SELECT 1 FROM conversations WHERE id = ? AND username = ?",
                    (conversation_id, username),
                ).fetchone()
                if owner_row is None:
                    conn.execute("ROLLBACK")
                    raise PermissionError("conversation_not_owned")

                next_seq_row = conn.execute(
                    "SELECT COALESCE(MAX(sequence_no), 0) + 1 FROM messages WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()
                next_seq = int(next_seq_row[0]) if next_seq_row else 1

                conn.execute(
                    "INSERT INTO messages (id, conversation_id, username, role, content, "
                    "payload_json, sequence_no, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        msg_id,
                        conversation_id,
                        username,
                        role_safe,
                        content or "",
                        payload_text,
                        next_seq,
                        now,
                    ),
                )
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
                conn.execute("COMMIT")
                return msg_id
            except PermissionError:
                raise
            except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
                last_exc = exc
                try:
                    conn.execute("ROLLBACK")
                except Exception:  # noqa: BLE001
                    pass
                # retry next attempt
            finally:
                conn.close()

    raise RuntimeError(f"append_message_failed_after_retries: {last_exc}")


def list_messages(
    conversation_id: str,
    username: str,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Return up to `limit` most-recent messages in chronological order.
    Verifies ownership via JOIN inside the same statement."""
    if not conversation_id or not username:
        return []
    init_db()
    capped_limit = max(1, min(int(limit or 24), 200))
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT m.id, m.role, m.content, m.payload_json, m.created_at, m.sequence_no
                FROM messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE m.conversation_id = ? AND c.username = ?
                ORDER BY m.sequence_no DESC
                LIMIT ?
                """,
                (conversation_id, username, capped_limit),
            ).fetchall()
        finally:
            conn.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        payload: Any
        try:
            payload = json.loads(r[3]) if r[3] else None
        except (TypeError, ValueError):
            payload = None
        out.append(
            {
                "id": r[0],
                "role": r[1],
                "content": r[2],
                "payload": payload,
                "created_at": int(r[4]) if r[4] is not None else 0,
                "sequence_no": int(r[5]) if r[5] is not None else 0,
            }
        )
    out.reverse()
    return out


def search_conversations(
    username: str,
    query: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Server-side search across conversation titles + message content for one
    user. Uses simple LIKE (FTS5 isn't compiled into all SQLite builds — the
    LIKE plan is fine for <10k conversations per user). Ranking: title hits
    first, then most-recently-updated."""
    if not username or not query:
        return []
    init_db()
    pattern = f"%{query.strip()}%"
    capped = max(1, min(int(limit or 30), 100))
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.updated_at,
                       (SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS msg_count,
                       (SELECT MAX(m.content) FROM messages m
                          WHERE m.conversation_id=c.id AND m.content LIKE ?
                          ORDER BY m.sequence_no DESC LIMIT 1) AS snippet
                FROM conversations c
                WHERE c.username = ?
                  AND (c.title LIKE ?
                       OR EXISTS (
                          SELECT 1 FROM messages m
                          WHERE m.conversation_id=c.id AND m.content LIKE ?
                       ))
                ORDER BY (c.title LIKE ?) DESC, c.updated_at DESC
                LIMIT ?
                """,
                (pattern, username, pattern, pattern, pattern, capped),
            ).fetchall()
        finally:
            conn.close()

    return [
        {
            "id": r[0],
            "title": r[1] or "(no title)",
            "updated_at": int(r[2]) if r[2] is not None else 0,
            "message_count": int(r[3]) if r[3] is not None else 0,
            "snippet": ((r[4] or "")[:200]) if r[4] else None,
        }
        for r in rows
    ]


def export_conversation(
    username: str, conversation_id: str
) -> dict[str, Any] | None:
    """Return a self-contained JSON dump of a conversation (metadata + every
    message + payloads). For user-driven `/export` endpoint."""
    if not username or not conversation_id:
        return None
    init_db()
    with _lock:
        conn = _connect()
        try:
            conv = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations "
                "WHERE id=? AND username=?",
                (conversation_id, username),
            ).fetchone()
            if not conv:
                return None
            msgs = conn.execute(
                """
                SELECT id, role, content, payload_json, created_at, sequence_no
                FROM messages WHERE conversation_id=? ORDER BY sequence_no ASC
                """,
                (conversation_id,),
            ).fetchall()
        finally:
            conn.close()

    def _payload(raw: Any) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    return {
        "version": _SCHEMA_VERSION,
        "exported_at": _now_ts(),
        "conversation": {
            "id": conv[0],
            "title": conv[1],
            "created_at": int(conv[2] or 0),
            "updated_at": int(conv[3] or 0),
        },
        "messages": [
            {
                "id": m[0],
                "role": m[1],
                "content": m[2],
                "payload": _payload(m[3]),
                "created_at": int(m[4] or 0),
                "sequence_no": int(m[5] or 0),
            }
            for m in msgs
        ],
    }


# Make sure schema exists on import (mirrors userstore pattern).
try:
    init_db()
except Exception:  # noqa: BLE001
    pass
