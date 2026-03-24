"""Data services for dashboard endpoints."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlparse

import requests
from psycopg.rows import dict_row
from requests.exceptions import SSLError

from src.agent.db.connection import get_connection


def _nota_media_por_sdr() -> dict[str, float]:
    query = """
        SELECT sdr_origem, ROUND(AVG(nota)::numeric, 2) AS media
        FROM avaliacao_log
        GROUP BY sdr_origem
        ORDER BY sdr_origem
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return {str(row["sdr_origem"]): float(row["media"]) for row in rows} if rows else {}


def _taxa_aprovacao_primeira_tentativa_por_sdr() -> dict[str, float]:
    query = """
        SELECT
          sdr_origem,
          ROUND(
            COUNT(*) FILTER (WHERE tentativas = 1 AND aprovado = true)::numeric
            / NULLIF(COUNT(*), 0) * 100, 1
          ) AS taxa
        FROM avaliacao_log
        GROUP BY sdr_origem
        ORDER BY sdr_origem
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return {str(row["sdr_origem"]): float(row["taxa"] or 0.0) for row in rows} if rows else {}


def _alertas_recentes(limite: int = 20) -> list[dict[str, Any]]:
    query = """
        SELECT id, lead_id, sdr_origem, nota, tentativas, criado_em
        FROM avaliacao_log
        WHERE aprovado = false AND tentativas >= 3
        ORDER BY criado_em DESC
        LIMIT %(limite)s
    """
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, {"limite": int(limite)})
            rows = cur.fetchall()
    return [dict(row) for row in rows] if rows else []


def _rabbitmq_auth() -> tuple[str, str]:
    user = os.getenv("RABBITMQ_MGMT_USER", "guest")
    password = os.getenv("RABBITMQ_MGMT_PASS", "guest")
    return user, password


def _rabbitmq_base() -> str:
    return os.getenv("RABBITMQ_MGMT_URL", "http://rabbitmq_rabbitmq:15672").rstrip("/")


def _rabbitmq_vhost_candidates() -> list[str]:
    """Return candidate RabbitMQ vhosts from env and AMQP URI."""
    candidates: list[str] = []

    configured = (os.getenv("RABBITMQ_MGMT_VHOST") or "").strip()
    if configured:
        candidates.append(configured)

    amqp_uri = (os.getenv("RABBITMQ_URI") or os.getenv("RABBITMQ_URL") or "").strip()
    if amqp_uri:
        parsed = urlparse(amqp_uri)
        if parsed.path and parsed.path != "/":
            candidates.append(parsed.path.lstrip("/"))

    candidates.append("/")

    unique: list[str] = []
    for item in candidates:
        value = item or "/"
        if value not in unique:
            unique.append(value)
    return unique


def _safe_request(url: str, headers: dict[str, str] | None = None, auth: tuple[str, str] | None = None) -> Any:
    """GET JSON with internal HTTPS->HTTP fallback for service DNS names."""
    try:
        response = requests.get(url, headers=headers or {}, auth=auth, timeout=10)
        response.raise_for_status()
        return response.json()
    except SSLError:
        if not url.startswith("https://"):
            raise
        fallback_url = "http://" + url[len("https://") :]
        response = requests.get(fallback_url, headers=headers or {}, auth=auth, timeout=10)
        response.raise_for_status()
        return response.json()


def get_overview() -> dict[str, Any]:
    """Build high-level dashboard overview from Postgres."""
    now = datetime.now(UTC)
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM leads")
            leads_total = int((cur.fetchone() or {}).get("total", 0))

            cur.execute("SELECT COUNT(*) AS total FROM leads WHERE criado_em >= NOW() - INTERVAL '24 hours'")
            leads_24h = int((cur.fetchone() or {}).get("total", 0))

            cur.execute("SELECT COUNT(*) AS total FROM disparos WHERE disparado_em >= NOW() - INTERVAL '24 hours'")
            disparos_24h = int((cur.fetchone() or {}).get("total", 0))

            cur.execute("SELECT COUNT(*) AS total FROM agendamentos WHERE criado_em >= NOW() - INTERVAL '24 hours'")
            agendamentos_24h = int((cur.fetchone() or {}).get("total", 0))

            cur.execute(
                """
                SELECT ROUND(AVG(nota)::numeric, 2) AS media
                FROM avaliacao_log
                WHERE criado_em >= NOW() - INTERVAL '7 days'
                """
            )
            nota_media_7d = float((cur.fetchone() or {}).get("media") or 0.0)

            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM avaliacao_log
                WHERE aprovado = false AND tentativas >= 3 AND criado_em >= NOW() - INTERVAL '7 days'
                """
            )
            alertas_7d = int((cur.fetchone() or {}).get("total", 0))

    return {
        "timestamp": now.isoformat(),
        "leads_total": leads_total,
        "leads_24h": leads_24h,
        "disparos_24h": disparos_24h,
        "agendamentos_24h": agendamentos_24h,
        "nota_media_7d": nota_media_7d,
        "alertas_7d": alertas_7d,
    }


def get_quality() -> dict[str, Any]:
    """Build quality payload for SDR scorecards and alerts."""
    return {
        "nota_media_por_sdr": _nota_media_por_sdr(),
        "taxa_aprovacao_primeira_tentativa_por_sdr": _taxa_aprovacao_primeira_tentativa_por_sdr(),
        "alertas_recentes": _alertas_recentes(limite=20),
    }


def _queue_snapshot(queue_name: str, vhost: str) -> dict[str, Any]:
    base = _rabbitmq_base()
    encoded_vhost = quote(vhost or "/", safe="")
    url = f"{base}/api/queues/{encoded_vhost}/{queue_name}"
    data = _safe_request(url, auth=_rabbitmq_auth())
    if not isinstance(data, dict):
        raise ValueError("Resposta invalida")
    return {
        "name": queue_name,
        "vhost": vhost,
        "messages": int(data.get("messages", 0)),
        "messages_ready": int(data.get("messages_ready", 0)),
        "messages_unacknowledged": int(data.get("messages_unacknowledged", 0)),
        "consumers": int(data.get("consumers", 0)),
        "state": str(data.get("state", "unknown")),
    }


def _queue_snapshot_safe(queue_name: str) -> dict[str, Any]:
    last_error = "erro desconhecido"
    for vhost in _rabbitmq_vhost_candidates():
        try:
            return _queue_snapshot(queue_name, vhost)
        except Exception as exc:
            last_error = f"vhost={vhost}: {exc}"

    return {
        "name": queue_name,
        "vhost": "N/A",
        "error": last_error,
        "messages": 0,
        "messages_ready": 0,
        "messages_unacknowledged": 0,
        "consumers": 0,
        "state": "unavailable",
    }


def get_queues() -> dict[str, Any]:
    """Return queue metrics from RabbitMQ management API."""
    queue_names = [
        "leads_entrada",
        "leads_disparo",
        "leads_entrada.dlq",
        "leads_disparo.dlq",
    ]
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "queues": [_queue_snapshot_safe(name) for name in queue_names],
    }


def get_integrations() -> dict[str, Any]:
    """Return integration health summary."""
    checks: list[dict[str, Any]] = []

    # Database
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        checks.append({"name": "postgres", "ok": True, "detail": "conectado"})
    except Exception as exc:
        checks.append({"name": "postgres", "ok": False, "detail": str(exc)})

    # Rabbit management API
    try:
        overview = _safe_request(f"{_rabbitmq_base()}/api/overview", auth=_rabbitmq_auth())
        if not isinstance(overview, dict):
            raise ValueError("Resposta invalida")
        checks.append(
            {
                "name": "rabbitmq",
                "ok": True,
                "detail": f"cluster {overview.get('cluster_name', 'N/A')}",
            }
        )
    except Exception as exc:
        checks.append({"name": "rabbitmq", "ok": False, "detail": str(exc)})

    # Chatwoot
    chatwoot_url = os.getenv("CHATWOOT_URL", "").rstrip("/")
    chatwoot_token = os.getenv("CHATWOOT_API_TOKEN", "")
    if chatwoot_url and chatwoot_token:
        try:
            profile = _safe_request(
                f"{chatwoot_url}/api/v1/profile",
                headers={"api_access_token": chatwoot_token},
            )
            if not isinstance(profile, dict):
                raise ValueError("Resposta invalida")
            checks.append({"name": "chatwoot", "ok": True, "detail": "conectado"})
        except Exception as exc:
            checks.append({"name": "chatwoot", "ok": False, "detail": str(exc)})
    else:
        checks.append({"name": "chatwoot", "ok": False, "detail": "nao configurado"})

    # Evolution
    evolution_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    evolution_api_key = os.getenv("EVOLUTION_API_KEY", "")
    if evolution_url and evolution_api_key:
        try:
            payload = _safe_request(
                f"{evolution_url}/instance/fetchInstances",
                headers={"apikey": evolution_api_key},
            )
            if not isinstance(payload, (dict, list)):
                raise ValueError("Resposta invalida")
            checks.append({"name": "evolution", "ok": True, "detail": "conectado"})
        except Exception as exc:
            checks.append({"name": "evolution", "ok": False, "detail": str(exc)})
    else:
        checks.append({"name": "evolution", "ok": False, "detail": "nao configurado"})

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }
