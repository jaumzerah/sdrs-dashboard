"""Cookie-based auth helpers for dashboard."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthSession:
    """Authenticated user session."""

    username: str
    expires_at: int


def _session_secret() -> str:
    return os.getenv("DASHBOARD_SESSION_SECRET", "change-me-dashboard-session-secret")


def _session_ttl_seconds() -> int:
    raw = os.getenv("DASHBOARD_SESSION_TTL_SECONDS", "28800")
    try:
        return max(300, int(raw))
    except ValueError:
        return 28800


def _sign(payload: str) -> str:
    return hmac.new(_session_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_cookie_value(username: str) -> str:
    """Create signed cookie payload for authenticated session."""
    expires_at = int(time.time()) + _session_ttl_seconds()
    payload = f"{username}|{expires_at}"
    return f"{payload}|{_sign(payload)}"


def parse_cookie_value(raw_value: str | None) -> AuthSession | None:
    """Validate and parse cookie value."""
    if not raw_value:
        return None

    parts = raw_value.split("|")
    if len(parts) != 3:
        return None

    username, expires_raw, provided_sig = parts
    payload = f"{username}|{expires_raw}"
    expected_sig = _sign(payload)

    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    try:
        expires_at = int(expires_raw)
    except ValueError:
        return None

    if expires_at < int(time.time()):
        return None

    return AuthSession(username=username, expires_at=expires_at)


def validate_credentials(username: str, password: str) -> bool:
    """Validate login credentials from environment."""
    expected_user = os.getenv("DASHBOARD_ADMIN_USER", "admin")
    expected_pass = os.getenv("DASHBOARD_ADMIN_PASSWORD", "admin")
    return hmac.compare_digest(username, expected_user) and hmac.compare_digest(password, expected_pass)
