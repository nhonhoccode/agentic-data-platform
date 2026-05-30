"""Lightweight session token for the demo login screen.

Token format: ``<payload_b64>.<sig_b64>`` where ``payload`` is
``f"{username}|{exp_unix_ts}"`` and ``sig`` is the HMAC-SHA256 of payload
keyed with ``Settings.resolved_session_secret``. URL-safe base64, no padding.

Compared to JWT this is *intentionally* minimal — no JSON, no algorithms list,
no audience claim. For an internal demo with a single admin user.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class SessionClaims:
    username: str
    exp: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload: bytes, secret: str) -> bytes:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()


def issue_token(username: str, *, ttl_sec: int | None = None) -> str:
    settings = get_settings()
    ttl = ttl_sec if ttl_sec is not None else settings.app_session_ttl_sec
    exp = int(time.time()) + max(60, int(ttl))
    payload = f"{username}|{exp}".encode("utf-8")
    sig = _sign(payload, settings.resolved_session_secret)
    return f"{_b64encode(payload)}.{_b64encode(sig)}"


def verify_token(token: str) -> SessionClaims | None:
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _b64decode(payload_b64)
        sig = _b64decode(sig_b64)
    except Exception:  # noqa: BLE001
        return None

    settings = get_settings()
    expected = _sign(payload, settings.resolved_session_secret)
    if not hmac.compare_digest(sig, expected):
        return None

    try:
        text = payload.decode("utf-8")
        username, exp_text = text.rsplit("|", 1)
        exp = int(exp_text)
    except Exception:  # noqa: BLE001
        return None

    if exp < int(time.time()):
        return None

    return SessionClaims(username=username, exp=exp)


def check_credentials(username: str, password: str) -> bool:
    """Constant-time check against env-configured admin credentials."""
    settings = get_settings()
    user_ok = hmac.compare_digest(
        (username or "").strip(), settings.app_admin_username
    )
    pass_ok = hmac.compare_digest(password or "", settings.app_admin_password)
    return user_ok and pass_ok


def generate_dev_secret() -> str:
    """Generate a strong secret for first-time .env bootstrap (not used at runtime)."""
    return secrets.token_urlsafe(32)
