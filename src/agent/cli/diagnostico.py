"""CLI diagnostics for local SDR system integrations."""

from __future__ import annotations

import io
import os
import sys
from typing import Any

import pika
import requests
from dotenv import load_dotenv
from pika.exceptions import AMQPError

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _fmt_status(ok: bool, text: str) -> str:
    prefix = "[✓]" if ok else "[✗]"
    return f"{prefix} {text}"


def _check_rabbitmq(queue_name: str = "leads_entrada") -> tuple[bool, str]:
    rabbitmq_uri = os.getenv("RABBITMQ_URI", "amqp://guest:guest@localhost:5672/")
    connection: pika.BlockingConnection | None = None
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_uri))
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, passive=True)
        return True, f"RabbitMQ — conectado (fila {queue_name} existe)"
    except AMQPError as exc:
        return False, f"RabbitMQ — erro: {exc}"
    finally:
        if connection and connection.is_open:
            connection.close()


def _check_chatwoot_profile() -> tuple[bool, str]:
    base_url = os.getenv("CHATWOOT_URL", "").rstrip("/")
    token = os.getenv("CHATWOOT_API_TOKEN", "")
    account_id = os.getenv("CHATWOOT_ACCOUNT_ID", "")

    if not base_url or not token:
        return False, "Chatwoot — erro: variáveis CHATWOOT_URL/CHATWOOT_API_TOKEN não configuradas"

    try:
        response = requests.get(
            f"{base_url}/api/v1/profile",
            headers={"api_access_token": token},
            timeout=20,
        )
        response.raise_for_status()
        account_text = account_id if account_id else "N/A"
        return True, f"Chatwoot — conectado (account {account_text})"
    except requests.RequestException as exc:
        return False, f"Chatwoot — erro: {exc}"


def _check_langsmith_env() -> tuple[bool, str]:
    tracing = str(os.getenv("LANGSMITH_TRACING", "")).lower() == "true"
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    project = os.getenv("LANGSMITH_PROJECT", "") or "N/A"

    key_ok = bool(api_key and api_key != "sua_chave_aqui")
    if tracing and key_ok:
        return True, f"LangSmith — tracing ativo (projeto {project})"
    return False, "LangSmith — erro: LANGSMITH_TRACING/API_KEY não configurados"


def main() -> None:
    load_dotenv()

    from agent.db.connection import get_connection
    from agent.integrations.evolution import EvolutionClient

    print("=== DIAGNÓSTICO DO SISTEMA ===")
    print()

    # Postgres
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database()")
                row = cur.fetchone()
                db_name = str(row[0]) if row else "desconhecido"
        print(_fmt_status(True, f"Postgres — conectado ({db_name})"))
    except Exception as exc:
        print(_fmt_status(False, f"Postgres — erro: {exc}"))

    # RabbitMQ
    ok_rabbit, msg_rabbit = _check_rabbitmq(queue_name="leads_entrada")
    print(_fmt_status(ok_rabbit, msg_rabbit))

    # Evolution API
    try:
        status_payload: dict[str, Any] = EvolutionClient().obter_status_instancia()
        if isinstance(status_payload.get("data"), list):
            print(_fmt_status(True, "Evolution API — conectado"))
        else:
            print(_fmt_status(True, "Evolution API — conectado"))
    except Exception as exc:
        print(_fmt_status(False, f"Evolution API — erro: {exc}"))

    # Chatwoot
    ok_chatwoot, msg_chatwoot = _check_chatwoot_profile()
    print(_fmt_status(ok_chatwoot, msg_chatwoot))

    # LangSmith
    ok_langsmith, msg_langsmith = _check_langsmith_env()
    print(_fmt_status(ok_langsmith, msg_langsmith))


if __name__ == "__main__":
    main()
