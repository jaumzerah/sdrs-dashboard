"""FastAPI service for SDR operations dashboard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from agent.agents.agendamento import DEFAULT_PROMPT_AGENDAMENTO
from agent.agents.sdr_anuncios import DEFAULT_PROMPT_ANUNCIOS
from agent.agents.sdr_frios import DEFAULT_PROMPT_FRIOS
from agent.agents.sdr_quentes import DEFAULT_PROMPT_QUENTES
from agent.db import prompt_repo
from agent.prompts.runtime import invalidate_prompt_cache
from dashboard_app.auth import (
    AuthSession,
    issue_cookie_value,
    parse_cookie_value,
    validate_credentials,
)
from dashboard_app.services import (
    get_integrations,
    get_overview,
    get_quality,
    get_queues,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
SESSION_COOKIE_NAME = "sdr_dashboard_session"

DEFAULT_PROMPTS = {
    "sdr_frios": DEFAULT_PROMPT_FRIOS,
    "sdr_quentes": DEFAULT_PROMPT_QUENTES,
    "sdr_anuncios": DEFAULT_PROMPT_ANUNCIOS,
    "sdr_agendamento": DEFAULT_PROMPT_AGENDAMENTO,
}


class LoginRequest(BaseModel):
    username: str
    password: str


class PromptDraftRequest(BaseModel):
    prompt_key: str = Field(min_length=3, max_length=100)
    content: str = Field(min_length=20)
    notes: str | None = Field(default=None, max_length=500)


class PromptPublishRequest(BaseModel):
    prompt_key: str = Field(min_length=3, max_length=100)
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


class PromptRollbackRequest(BaseModel):
    prompt_key: str = Field(min_length=3, max_length=100)
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=500)


def _base_app() -> FastAPI:
    app = FastAPI(title="SDR Dashboard API", version="1.0.0")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app


app = _base_app()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    return response


def _require_session(request: Request) -> AuthSession:
    session = parse_cookie_value(request.cookies.get(SESSION_COOKIE_NAME))
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao invalida")
    return session


def _bootstrap_prompt_keys() -> None:
    for key, content in DEFAULT_PROMPTS.items():
        try:
            versions = prompt_repo.list_versions(key, limit=1)
            if versions:
                continue
        except Exception:
            pass
        prompt_repo.ensure_prompt_exists(key, content)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
def dashboard_page(request: Request) -> Response:
    session = parse_cookie_value(request.cookies.get(SESSION_COOKIE_NAME))
    if not session:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("dashboard.html", {"request": request, "username": session.username})


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> Response:
    if not validate_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais invalidas")

    cookie_value = issue_cookie_value(payload.username)
    response = JSONResponse({"ok": True, "username": payload.username})
    cookie_secure = str(os.getenv("DASHBOARD_COOKIE_SECURE", "true")).lower() == "true"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/auth/logout")
def logout(_: AuthSession = Depends(_require_session)) -> Response:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@app.get("/api/auth/me")
def me(session: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    return {"authenticated": True, "username": session.username, "expires_at": session.expires_at}


@app.get("/api/dashboard/overview")
def dashboard_overview(_: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    return get_overview()


@app.get("/api/dashboard/quality")
def dashboard_quality(_: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    return get_quality()


@app.get("/api/dashboard/queues")
def dashboard_queues(_: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    return get_queues()


@app.get("/api/dashboard/integrations")
def dashboard_integrations(_: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    return get_integrations()


@app.get("/api/prompts")
def list_prompts(_: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    _bootstrap_prompt_keys()
    payload: dict[str, Any] = {}
    for key in prompt_repo.list_prompt_keys():
        versions = prompt_repo.list_versions(key, limit=20)
        payload[key] = [
            {
                "version": item.version,
                "status": item.status,
                "created_by": item.created_by,
                "notes": item.notes,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "published_at": item.published_at.isoformat() if item.published_at else None,
                "rollback_of": item.rollback_of,
                "content": item.content,
            }
            for item in versions
        ]
    return {"prompts": payload}


@app.post("/api/prompts/draft")
def create_prompt_draft(payload: PromptDraftRequest, session: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    version = prompt_repo.create_draft(
        prompt_key=payload.prompt_key,
        content=payload.content,
        actor=session.username,
        notes=payload.notes,
    )
    return {
        "ok": True,
        "prompt_key": version.prompt_key,
        "version": version.version,
        "status": version.status,
    }


@app.post("/api/prompts/publish")
def publish_prompt(payload: PromptPublishRequest, session: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    published = prompt_repo.publish_version(
        prompt_key=payload.prompt_key,
        version=payload.version,
        actor=session.username,
        reason=payload.reason,
    )
    invalidate_prompt_cache(payload.prompt_key)
    return {
        "ok": True,
        "prompt_key": published.prompt_key,
        "version": published.version,
        "status": published.status,
    }


@app.post("/api/prompts/rollback")
def rollback_prompt(payload: PromptRollbackRequest, session: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    restored = prompt_repo.rollback_to_version(
        prompt_key=payload.prompt_key,
        version=payload.version,
        actor=session.username,
        reason=payload.reason,
    )
    invalidate_prompt_cache(payload.prompt_key)
    return {
        "ok": True,
        "prompt_key": restored.prompt_key,
        "version": restored.version,
        "status": restored.status,
    }


@app.get("/api/prompts/audit")
def prompt_audit(_: AuthSession = Depends(_require_session)) -> dict[str, Any]:
    logs = prompt_repo.list_recent_audit(limit=100)
    normalized = []
    for row in logs:
        normalized.append(
            {
                **row,
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
        )
    return {"events": normalized}


def main() -> None:
    """Run dashboard API server."""
    port_raw = os.getenv("DASHBOARD_PORT", os.getenv("PORT", "3000"))
    try:
        port = int(port_raw)
    except ValueError:
        port = 3000
    uvicorn.run("dashboard_app.main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
