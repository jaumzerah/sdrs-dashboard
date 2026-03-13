"""RabbitMQ consumer for inbound lead events."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import pika
from pika.exceptions import AMQPConnectionError
from dotenv import load_dotenv
from langchain_core.messages import AIMessage

from agent.agents.supervisor import preparar_entrada_supervisor
from agent.db.checkpoint_migration import migrar_thread_se_necessario
from agent.db.leads_repo import atualizar_lead, buscar_lead, criar_lead
from agent.integrations.chatwoot import ChatwootClient
from agent.integrations.evolution import EvolutionClient
from agent.routing.rules import route_target_from_classificacao
from agent.utils.classifier import classificar_origem

logger = logging.getLogger(__name__)
_GRAPH: Any | None = None


def _get_graph() -> Any:
    """Lazy-load graph after environment variables are loaded."""
    global _GRAPH
    if _GRAPH is None:
        from agent.graph import graph

        _GRAPH = graph
    return _GRAPH


def _extract_content(message: Any) -> str:
    """Extract content text from dict or LangChain message objects."""
    if isinstance(message, dict):
        content = message.get("content")
        return content if isinstance(content, str) else str(content)
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _extract_final_message_text(result: dict[str, Any]) -> str:
    """Get final text from graph invoke result."""
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return ""
    return _extract_content(messages[-1]).strip()


def _extract_last_ai_message_text(result: dict[str, Any]) -> str:
    """Get latest AIMessage content from graph result."""
    messages = result.get("messages")
    if not isinstance(messages, list) or not messages:
        return ""

    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return _extract_content(message).strip()
    return ""


class LeadConsumer:
    """Consume lead events from RabbitMQ and run SDR supervisor."""

    def __init__(self, rabbitmq_uri: str, queue_name: str = "leads_entrada") -> None:
        self.rabbitmq_uri = rabbitmq_uri
        self.queue_name = queue_name
        self.chatwoot = self._build_chatwoot_client()
        self.evolution = self._build_evolution_client()

    def _build_chatwoot_client(self) -> ChatwootClient | None:
        """Create Chatwoot client if environment is configured."""
        try:
            return ChatwootClient()
        except ValueError:
            logger.warning("Chatwoot nao configurado. Continuando sem sincronizacao CRM")
            return None

    def _build_evolution_client(self) -> EvolutionClient | None:
        """Create Evolution client if environment is configured."""
        try:
            return EvolutionClient()
        except ValueError:
            logger.warning("Evolution nao configurado. Continuando sem envio WhatsApp")
            return None

    def _enviar_resposta_whatsapp(self, id_primario: str, numero: str | None, texto: str) -> None:
        """Send generated response to WhatsApp when phone is available."""
        if not texto:
            return
        if not numero:
            logger.warning("Lead %s sem número — resposta não enviada", id_primario)
            return
        if not self.evolution:
            return

        try:
            self.evolution.enviar_mensagem(numero=str(numero), texto=texto)
        except Exception:
            logger.exception("Falha ao enviar mensagem via Evolution para %s", numero)

    def _labels_from_classificacao(self, classificacao: dict[str, Any]) -> list[str]:
        """Map lead classification to Chatwoot labels."""
        origem = str(classificacao.get("origem", "")).lower()
        plataforma = str(classificacao.get("plataforma", "")).lower()

        if origem == "disparo":
            return ["lead_frio"]
        if origem == "organico":
            return ["lead_quente"]
        if origem == "anuncio":
            if plataforma == "google":
                return ["anuncio_google"]
            return ["anuncio_meta"]
        return []

    def _build_chatwoot_note_inicial(self, classificacao: dict[str, Any]) -> str:
        """Build initial private note for Chatwoot conversation context."""
        id_lead = classificacao.get("id_lead", {})
        tipo_id = "LID" if id_lead.get("usando_lid") else "JID"
        campanha = classificacao.get("campanha") or "N/A"
        return (
            f"Lead recebido via {classificacao.get('canal')}. "
            f"Origem: {classificacao.get('origem')}. "
            f"Campanha: {campanha}. "
            f"Identificador: {id_lead.get('id_primario')} ({tipo_id})."
        )

    @staticmethod
    def _extract_contact_id(contato: dict[str, Any]) -> int:
        """Extract contact id from Chatwoot response payloads."""
        if "id" in contato:
            return int(contato["id"])
        payload = contato.get("payload")
        if isinstance(payload, dict) and "id" in payload:
            return int(payload["id"])
        raise ValueError("Nao foi possivel identificar contact_id no retorno do Chatwoot")

    @staticmethod
    def _extract_conversation_id(conversa: dict[str, Any]) -> int:
        """Extract conversation id from Chatwoot response payloads."""
        if "id" in conversa:
            return int(conversa["id"])
        payload = conversa.get("payload")
        if isinstance(payload, dict) and "id" in payload:
            return int(payload["id"])
        raise ValueError("Nao foi possivel identificar conversation_id no retorno do Chatwoot")

    def _sync_chatwoot(
        self,
        payload: dict[str, Any],
        classificacao: dict[str, Any],
        lead: dict[str, Any],
    ) -> int | None:
        """Sync lead context to Chatwoot and return conversation_id."""
        if not self.chatwoot:
            return None

        contact_id = lead.get("chatwoot_contact_id")
        if contact_id is None:
            nome = payload.get("pushName") or payload.get("nome") or "Lead"
            contato = self.chatwoot.buscar_ou_criar_contato(classificacao.get("id_lead", {}), nome=nome)
            contact_id = self._extract_contact_id(contato)
            lead_id = lead.get("id")
            if lead_id:
                lead = atualizar_lead(str(lead_id), {"chatwoot_contact_id": int(contact_id)})
        contact_id = int(contact_id)

        conversa = self.chatwoot.criar_conversa(contact_id=contact_id, inbox_id=self.chatwoot.inbox_id)
        conversation_id = self._extract_conversation_id(conversa)

        labels = self._labels_from_classificacao(classificacao)
        if labels:
            self.chatwoot.adicionar_label(conversation_id=conversation_id, labels=labels)

        nota = self._build_chatwoot_note_inicial(classificacao)
        self.chatwoot.adicionar_nota(conversation_id=conversation_id, nota=nota)
        return conversation_id

    def _upsert_lead(self, classificacao: dict[str, Any], app: Any) -> tuple[dict[str, Any], str]:
        """Create/update lead in Postgres and return DB record + thread_id."""
        id_lead = classificacao.get("id_lead", {})
        lid = id_lead.get("lid")
        jid = id_lead.get("jid")
        numero = id_lead.get("numero")
        id_primario = id_lead.get("id_primario") or lid or jid or "sem-id"

        lead = buscar_lead(lid=lid, jid=jid, numero=numero)
        if lead is None:
            lead = criar_lead(
                {
                    "lid": lid,
                    "jid": jid,
                    "numero": numero,
                    "usando_lid": bool(id_lead.get("usando_lid")),
                    "origem": classificacao.get("origem"),
                    "plataforma": classificacao.get("plataforma"),
                    "campanha": classificacao.get("campanha"),
                    "canal": classificacao.get("canal"),
                }
            )
            return lead, str(id_primario)

        if lid and not lead.get("lid"):
            jid_antigo = lead.get("jid")
            lead = atualizar_lead(str(lead.get("id")), {"lid": lid, "usando_lid": True})
            if isinstance(jid_antigo, str) and jid_antigo:
                migrar_thread_se_necessario(app, jid=jid_antigo, lid=lid)
            id_primario = lid

        return lead, str(id_primario)

    def _process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        app = _get_graph()
        classificacao = classificar_origem(payload)
        lead, thread_id = self._upsert_lead(classificacao, app)
        chatwoot_conversation_id = self._sync_chatwoot(payload, classificacao, lead)
        entrada = preparar_entrada_supervisor(classificacao)
        entrada["lead_id"] = str(lead.get("id")) if lead.get("id") else None
        entrada["chatwoot_conversation_id"] = chatwoot_conversation_id

        config = {"configurable": {"thread_id": thread_id}}
        result = app.invoke(entrada, config=config)

        texto_final = _extract_final_message_text(result)
        resposta_ao_lead = _extract_last_ai_message_text(result)
        numero = classificacao.get("id_lead", {}).get("numero")
        self._enviar_resposta_whatsapp(
            id_primario=thread_id,
            numero=str(numero) if numero is not None else None,
            texto=resposta_ao_lead,
        )
        sdr_acionado = route_target_from_classificacao(
            classificacao.get("origem"),
            classificacao.get("mensagem"),
        )

        logger.info(
            "Lead processado",
            extra={
                "origem": classificacao.get("origem"),
                "canal": classificacao.get("canal"),
                "sdr_acionado": sdr_acionado,
                "id_primario": thread_id,
                "lead_id": lead.get("id"),
                "chatwoot_conversation_id": chatwoot_conversation_id,
                "resposta": texto_final,
            },
        )

        return {
            "classificacao": classificacao,
            "lead_id": lead.get("id"),
            "thread_id": thread_id,
            "chatwoot_conversation_id": chatwoot_conversation_id,
            "sdr_acionado": sdr_acionado,
            "resposta": texto_final,
        }

    def _on_message(
        self,
        channel: Any,
        method: Any,
        properties: Any,
        body: bytes,
    ) -> None:
        del properties
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Payload deve ser um objeto JSON")

            key = payload.get("data", {}).get("key", {})
            if isinstance(key, dict) and bool(key.get("fromMe", False)):
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

            self._process_payload(payload)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError:
            logger.exception("Mensagem invalida na fila; descartando")
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logger.exception("Falha ao processar lead; enviando para retry")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def run(self) -> None:
        """Run consumer loop with automatic reconnection."""
        while True:
            connection: pika.BlockingConnection | None = None
            try:
                params = pika.URLParameters(self.rabbitmq_uri)
                connection = pika.BlockingConnection(params)
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=self.queue_name, on_message_callback=self._on_message)
                logger.info(
                    "Consumer conectado",
                    extra={"queue": self.queue_name, "rabbitmq_uri": self.rabbitmq_uri},
                )
                channel.start_consuming()
            except KeyboardInterrupt:
                logger.info("Consumer interrompido manualmente")
                break
            except AMQPConnectionError:
                logger.exception("Falha de conexao com RabbitMQ. Tentando novamente em 5s")
                time.sleep(5)
            finally:
                if connection and connection.is_open:
                    connection.close()


def main() -> None:
    """CLI entrypoint for RabbitMQ lead consumer."""
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    rabbitmq_uri = os.getenv("RABBITMQ_URI", "amqp://guest:guest@localhost:5672/")
    consumer = LeadConsumer(rabbitmq_uri=rabbitmq_uri, queue_name="leads_entrada")
    consumer.run()


if __name__ == "__main__":
    main()
