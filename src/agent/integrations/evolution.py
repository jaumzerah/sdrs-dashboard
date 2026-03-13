"""Evolution API integration client for WhatsApp send/health/config."""

from __future__ import annotations

import os
from typing import Any

import requests


class EvolutionClient:
    """Thin Evolution API client bound to one configured instance."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        instance: str | None = None,
        timeout: int = 30,
    ) -> None:
        base_url = base_url or os.getenv("EVOLUTION_API_URL", "")
        api_key = api_key or os.getenv("EVOLUTION_API_KEY", "")
        instance = instance or os.getenv("EVOLUTION_INSTANCE", "")

        if not base_url:
            raise ValueError("EVOLUTION_API_URL nao configurado")
        if not api_key:
            raise ValueError("EVOLUTION_API_KEY nao configurado")
        if not instance:
            raise ValueError("EVOLUTION_INSTANCE nao configurado")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.instance = instance
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = requests.request(
            method=method,
            url=f"{self.base_url}{path}",
            headers=self._headers,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"data": data}

    def configurar_rabbitmq_instancia(self) -> dict[str, Any]:
        """Enable RabbitMQ events for the configured instance."""
        return self._request(
            "POST",
            f"/rabbitmq/set/{self.instance}",
            json={
                "enabled": True,
                "events": ["MESSAGES_UPSERT"],
            },
        )

    def enviar_mensagem(self, numero: str, texto: str) -> dict[str, Any]:
        """Send a WhatsApp text message through Evolution API."""
        payload = {
            "number": str(numero),
            "text": str(texto),
        }
        return self._request(
            "POST",
            f"/message/sendText/{self.instance}",
            json=payload,
        )

    def obter_status_instancia(self) -> dict[str, Any]:
        """Fetch all instances status for diagnostics/health checks."""
        return self._request("GET", "/instance/fetchInstances")
