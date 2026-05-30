"""Lightweight SQLite-backed TTL cache for expensive external calls.

Used by:
- domain_filter.classify_in_domain  (1-day TTL)
- tools.web_search_tool             (1-hour TTL — content drifts faster)

Keyed by a SHA256 of the normalized query so cache hits work across whitespace
and case differences. Stored in `<data_dir>/agent_cache.db` so it survives
container recreates.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.config import get_settings

_lock = threading.RLock()


def _db_path() -> Path:
    base = Path(get_settings().data_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base / "agent_cache.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    expires_at INTEGER NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_exp ON cache(expires_at)")
        finally:
            conn.close()


def _hash_key(text: str) -> str:
    norm = " ".join((text or "").lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def get(namespace: str, query: str) -> Any | None:
    """Return cached value or None. Drops the row if expired."""
    try:
        _init()
        key = _hash_key(query)
        now = int(time.time())
        with _lock:
            conn = _connect()
            try:
                row = conn.execute(
                    "SELECT value, expires_at FROM cache WHERE namespace=? AND key=?",
                    (namespace, key),
                ).fetchone()
                if not row:
                    return None
                value, exp = row
                if exp < now:
                    conn.execute(
                        "DELETE FROM cache WHERE namespace=? AND key=?",
                        (namespace, key),
                    )
                    return None
                return json.loads(value)
            finally:
                conn.close()
    except Exception:  # noqa: BLE001 — cache must never crash the agent
        return None


def set(namespace: str, query: str, value: Any, ttl_sec: int) -> None:
    try:
        _init()
        key = _hash_key(query)
        exp = int(time.time()) + max(60, int(ttl_sec))
        payload = json.dumps(value, default=str, ensure_ascii=False)
        with _lock:
            conn = _connect()
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (namespace, key, value, expires_at) "
                    "VALUES (?,?,?,?)",
                    (namespace, key, payload, exp),
                )
            finally:
                conn.close()
    except Exception:  # noqa: BLE001
        pass


def purge_expired() -> int:
    """Sweep expired rows. Returns number of rows deleted."""
    try:
        _init()
        now = int(time.time())
        with _lock:
            conn = _connect()
            try:
                cur = conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
                return cur.rowcount or 0
            finally:
                conn.close()
    except Exception:  # noqa: BLE001
        return 0


# Best-effort init on import — same pattern as userstore / chatstore.
try:
    _init()
except Exception:  # noqa: BLE001
    pass
