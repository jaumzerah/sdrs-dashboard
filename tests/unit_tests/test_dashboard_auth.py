from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from dashboard_app import auth


def test_issue_and_parse_cookie_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("DASHBOARD_SESSION_TTL_SECONDS", "3600")

    raw = auth.issue_cookie_value("admin")
    session = auth.parse_cookie_value(raw)

    assert session is not None
    assert session.username == "admin"


def test_parse_cookie_rejects_invalid_signature(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_SESSION_SECRET", "test-secret")
    raw = auth.issue_cookie_value("admin")
    tampered = f"{raw}tampered"

    assert auth.parse_cookie_value(tampered) is None


def test_validate_credentials(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_ADMIN_USER", "sdr-admin")
    monkeypatch.setenv("DASHBOARD_ADMIN_PASSWORD", "super-secret")

    assert auth.validate_credentials("sdr-admin", "super-secret")
    assert not auth.validate_credentials("sdr-admin", "wrong")
