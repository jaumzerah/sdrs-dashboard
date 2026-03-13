"""Chatwoot integration client for SDR handoff workflows."""

from __future__ import annotations

import os
from typing import Any

import requests


class ChatwootClient:
    """Thin Chatwoot application API client.

    Environment variables used by default:
    - CHATWOOT_URL
    - CHATWOOT_API_TOKEN
    - CHATWOOT_ACCOUNT_ID
    - CHATWOOT_INBOX_ID
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
        account_id: int | None = None,
        inbox_id: int | None = None,
        timeout: int = 30,
    ) -> None:
        base_url = base_url or os.getenv("CHATWOOT_URL", "")
        api_token = api_token or os.getenv("CHATWOOT_API_TOKEN", "")
        account_raw = account_id if account_id is not None else os.getenv("CHATWOOT_ACCOUNT_ID", "")
        inbox_raw = inbox_id if inbox_id is not None else os.getenv("CHATWOOT_INBOX_ID", "")

        if not base_url:
            raise ValueError("CHATWOOT_URL nao configurado")
        if not api_token:
            raise ValueError("CHATWOOT_API_TOKEN nao configurado")
        if not account_raw:
            raise ValueError("CHATWOOT_ACCOUNT_ID nao configurado")
        if not inbox_raw:
            raise ValueError("CHATWOOT_INBOX_ID nao configurado")

        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.account_id = int(account_raw)
        self.inbox_id = int(inbox_raw)
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "api_access_token": self.api_token,
            "Content-Type": "application/json",
        }

    def _account_url(self, path: str) -> str:
        return f"{self.base_url}/api/v1/accounts/{self.account_id}{path}"

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = requests.request(
            method=method,
            url=self._account_url(path),
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

    def _buscar_contato_por_telefone(self, phone_number: str) -> dict[str, Any] | None:
        """Find contact by phone number using search endpoint."""
        if not phone_number:
            return None

        payload = self._request("GET", "/contacts/search", params={"q": phone_number})
        candidates = payload.get("payload", [])
        if not isinstance(candidates, list):
            return None

        for item in candidates:
            if not isinstance(item, dict):
                continue
            if str(item.get("phone_number", "")) == str(phone_number):
                return item

        for item in candidates:
            if isinstance(item, dict):
                return item
        return None

    def _atualizar_contato(self, contact_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Update contact fields."""
        return self._request("PUT", f"/contacts/{contact_id}", json=body)

    def buscar_ou_criar_contato(self, id_lead: dict[str, Any], nome: str | None = None) -> dict[str, Any]:
        """Search contact by number and create/update when needed."""
        numero = id_lead.get("numero")
        lid = id_lead.get("lid")
        jid = id_lead.get("jid")
        usando_lid = bool(id_lead.get("usando_lid"))
        identifier = lid or jid

        if not numero:
            raise ValueError("id_lead.numero e obrigatorio para buscar ou criar contato")

        contato = self._buscar_contato_por_telefone(numero)

        custom_attributes = {
            "lid": lid,
            "jid": jid,
            "usando_lid": usando_lid,
        }

        if contato is None:
            body = {
                "inbox_id": self.inbox_id,
                "name": nome or "Lead WhatsApp",
                "phone_number": numero,
                "identifier": identifier,
                "custom_attributes": custom_attributes,
            }
            created = self._request("POST", "/contacts", json=body)
            return created.get("payload", created)

        contact_id = int(contato.get("id"))
        needs_update = bool(lid and contato.get("identifier") != lid)
        if needs_update:
            update_body = {
                "identifier": lid,
                "custom_attributes": {
                    **(contato.get("custom_attributes") or {}),
                    **custom_attributes,
                },
            }
            updated = self._atualizar_contato(contact_id, update_body)
            return updated.get("payload", updated)

        return contato

    def _listar_conversas_contato(self, contact_id: int) -> list[dict[str, Any]]:
        """List conversations for a given contact."""
        payload = self._request("GET", f"/contacts/{contact_id}/conversations")
        rows = payload.get("payload", payload.get("data", []))
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def _reabrir_conversa(self, conversation_id: int) -> dict[str, Any]:
        """Reopen conversation when not open."""
        return self._request(
            "POST",
            f"/conversations/{conversation_id}/toggle_status",
            json={"status": "open"},
        )

    def criar_conversa(self, contact_id: int, inbox_id: int) -> dict[str, Any]:
        """Create new conversation or reopen existing one for contact/inbox."""
        existentes = self._listar_conversas_contato(contact_id)
        for conversa in existentes:
            if int(conversa.get("inbox_id", 0)) != int(inbox_id):
                continue
            status = str(conversa.get("status", "open")).lower()
            conversation_id = int(conversa.get("id"))
            if status != "open":
                self._reabrir_conversa(conversation_id)
            return conversa

        body = {
            "source_id": f"lead-{contact_id}-{inbox_id}",
            "inbox_id": int(inbox_id),
            "contact_id": int(contact_id),
            "status": "open",
        }
        created = self._request("POST", "/conversations", json=body)
        return created.get("payload", created)

    def adicionar_label(self, conversation_id: int, labels: list[str]) -> None:
        """Attach labels to a conversation."""
        self._request(
            "POST",
            f"/conversations/{conversation_id}/labels",
            json={"labels": labels},
        )

    def adicionar_nota(self, conversation_id: int, nota: str) -> None:
        """Add private note to a conversation."""
        self._request(
            "POST",
            f"/conversations/{conversation_id}/messages",
            json={
                "content": nota,
                "message_type": "outgoing",
                "private": True,
            },
        )
