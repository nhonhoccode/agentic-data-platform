"""SQLite-backed user store for the demo UI.

Persists to ``<data_dir>/auth.db`` (mounted as a Docker volume so accounts
survive container recreates). Passwords are stored with PBKDF2-HMAC-SHA256
+ per-user random salt. No third-party dependency.

The admin user defined via APP_ADMIN_USERNAME/APP_ADMIN_PASSWORD is checked
*before* the DB — so it always works even on a fresh install.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
from typing import Any
import threading
from pathlib import Path

from app.config import get_settings

_PBKDF2_ITERS = 200_000
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")
_lock = threading.RLock()


def _db_path() -> Path:
    settings = get_settings()
    base = Path(settings.data_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base / "auth.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Tier-based access control. Higher tier ⊇ all features of lower tiers. The
# env-defined admin user (APP_ADMIN_USERNAME) is bootstrapped as tier=admin +
# is_admin=1 on first init so the system is never lockable-out.
# ---------------------------------------------------------------------------
TIER_BASIC = "basic"
TIER_APPROVED = "approved"
TIER_ADMIN = "admin"

_TIER_FEATURES: dict[str, set[str]] = {
    TIER_BASIC: {"chat"},
    TIER_APPROVED: {"chat", "web_search", "upload", "export"},
    TIER_ADMIN: {"chat", "web_search", "upload", "export", "admin"},
}


def tier_allows(tier: str | None, feature: str) -> bool:
    return feature in _TIER_FEATURES.get(tier or TIER_BASIC, set())


_USER_SCHEMA_VERSION = 2


def init_db() -> None:
    """Create / migrate the users table. PRAGMA user_version drives migrations."""
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            current = conn.execute("PRAGMA user_version").fetchone()
            version = int(current[0]) if current else 0

            if version < 2:
                # Migration 1 → 2: add tier + is_admin columns.
                cols = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(users)").fetchall()
                }
                if "tier" not in cols:
                    conn.execute(
                        "ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'basic'"
                    )
                if "is_admin" not in cols:
                    conn.execute(
                        "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0"
                    )
                conn.execute(f"PRAGMA user_version = {_USER_SCHEMA_VERSION}")

            # Bootstrap the env-defined admin so the system always has at least
            # one approver — idempotent UPSERT-ish.
            from app.config import get_settings  # local import to avoid cycle

            admin_username = (get_settings().app_admin_username or "admin").strip()
            if admin_username:
                conn.execute(
                    "UPDATE users SET tier='admin', is_admin=1 WHERE username=?",
                    (admin_username,),
                )
        finally:
            conn.close()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERS)
    return f"pbkdf2_sha256${_PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def _verify_hash(password: str, stored: str) -> bool:
    try:
        scheme, iters_text, salt_hex, expected_hex = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iters = int(iters_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return secrets.compare_digest(dk, expected)


class UserStoreError(Exception):
    pass


def validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username or ""):
        raise UserStoreError(
            "username phải dài 3-32 ký tự, chỉ chữ/số/._-"
        )


def validate_password(password: str) -> None:
    if not password or len(password) < 6:
        raise UserStoreError("password phải tối thiểu 6 ký tự")
    if len(password) > 256:
        raise UserStoreError("password tối đa 256 ký tự")


def create_user(username: str, password: str) -> None:
    validate_username(username)
    validate_password(password)
    init_db()
    with _lock:
        conn = _connect()
        try:
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, strftime('%s','now'))",
                    (username, _hash_password(password)),
                )
            except sqlite3.IntegrityError as exc:
                raise UserStoreError("username_taken") from exc
        finally:
            conn.close()


def verify_user(username: str, password: str) -> bool:
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return False
    return _verify_hash(password, row[0])


def user_exists(username: str) -> bool:
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        finally:
            conn.close()
    return row is not None


def user_count() -> int:
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        finally:
            conn.close()
    return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Tier / admin management — used by the auth endpoints + admin panel.
# ---------------------------------------------------------------------------


def get_user_info(username: str) -> dict[str, Any] | None:
    """Return {username, tier, is_admin, created_at} or None.

    Env-admin (APP_ADMIN_USERNAME) is treated as a virtual admin even if not
    present in the DB — they can always log in via env credentials.
    """
    if not username:
        return None
    init_db()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT username, tier, is_admin, created_at FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        finally:
            conn.close()
    if row:
        return {
            "username": row[0],
            "tier": row[1] or "basic",
            "is_admin": bool(row[2]),
            "created_at": int(row[3] or 0),
        }
    # Virtual env-admin (login via env credentials, never created in DB).
    from app.config import get_settings

    env_admin = (get_settings().app_admin_username or "admin").strip()
    if username == env_admin:
        return {
            "username": username,
            "tier": "admin",
            "is_admin": True,
            "created_at": 0,
        }
    return None


def is_admin(username: str) -> bool:
    info = get_user_info(username)
    return bool(info and info.get("is_admin"))


def has_feature(username: str, feature: str) -> bool:
    info = get_user_info(username)
    if not info:
        return False
    return tier_allows(info.get("tier"), feature)


def set_tier(username: str, tier: str) -> bool:
    if tier not in {"basic", "approved", "admin"}:
        raise UserStoreError("tier không hợp lệ")
    init_db()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE users SET tier=? WHERE username=?", (tier, username)
            )
            return cur.rowcount > 0
        finally:
            conn.close()


def set_is_admin(username: str, value: bool) -> bool:
    init_db()
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "UPDATE users SET is_admin=? WHERE username=?",
                (1 if value else 0, username),
            )
            return cur.rowcount > 0
        finally:
            conn.close()


def list_users() -> list[dict[str, Any]]:
    """Admin-facing list — username, tier, is_admin, created_at."""
    init_db()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT username, tier, is_admin, created_at FROM users "
                "ORDER BY created_at DESC"
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "username": r[0],
            "tier": r[1] or "basic",
            "is_admin": bool(r[2]),
            "created_at": int(r[3] or 0),
        }
        for r in rows
    ]


# Make sure the schema exists when the module is first imported by FastAPI.
try:
    init_db()
except Exception:  # noqa: BLE001
    # Defer errors to actual call sites; container startup must not crash.
    pass
