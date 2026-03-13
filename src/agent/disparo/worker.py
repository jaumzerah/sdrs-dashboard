"""RabbitMQ worker to send cold outreach messages."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import pika
from dotenv import load_dotenv
from pika.exceptions import AMQPConnectionError

logger = logging.getLogger(__name__)


class DisparoWorker:
    """Consume leads_disparo queue and send messages with retry."""

    def __init__(self, rabbitmq_uri: str, queue_name: str = "leads_disparo") -> None:
        self.rabbitmq_uri = rabbitmq_uri
        self.queue_name = queue_name
        self.delay_segundos = int(os.getenv("DISPARO_DELAY_SEGUNDOS", "30") or "30")

    def _on_message(self, channel: Any, method: Any, properties: Any, body: bytes) -> None:
        del properties

        from agent.db.disparos_repo import esta_na_base_disparados
        from agent.disparo.sender import enviar_disparo

        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Payload deve ser objeto JSON")

            id_primario = str(payload.get("id_primario", "") or "")
            numero = str(payload.get("numero", "") or "")

            logger.info("Processando lead de disparo", extra={"id_primario": id_primario, "numero": numero})
            ok = enviar_disparo(payload)

            if ok:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("Disparo confirmado e ACK aplicado", extra={"id_primario": id_primario, "numero": numero})
                time.sleep(self.delay_segundos)
                return

            existente = esta_na_base_disparados(lid=id_primario, jid=id_primario, numero=numero)
            if existente is not None:
                channel.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(
                    "Lead duplicado em disparos; ACK sem reenvio",
                    extra={"id_primario": id_primario, "numero": numero},
                )
                return

            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            logger.warning(
                "Falha de envio no disparo; NACK com requeue",
                extra={"id_primario": id_primario, "numero": numero},
            )
        except json.JSONDecodeError:
            logger.exception("Mensagem invalida na fila leads_disparo; descartando")
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logger.exception("Erro inesperado no worker de disparo; requeue")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def run(self) -> None:
        """Run worker loop with auto reconnection."""
        if not os.getenv("EVOLUTION_API_URL") or not os.getenv("EVOLUTION_API_KEY") or not os.getenv("EVOLUTION_INSTANCE_DISPARO"):
            logger.warning("Evolution disparo incompleto no .env; worker iniciara e aguardara mensagens")

        while True:
            connection: pika.BlockingConnection | None = None
            try:
                params = pika.URLParameters(self.rabbitmq_uri)
                connection = pika.BlockingConnection(params)
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=self.queue_name, on_message_callback=self._on_message)
                logger.info("Worker de disparo conectado", extra={"queue": self.queue_name})
                channel.start_consuming()
            except KeyboardInterrupt:
                logger.info("Worker de disparo interrompido manualmente")
                break
            except AMQPConnectionError:
                logger.exception("Falha de conexao com RabbitMQ. Tentando novamente em 5s")
                time.sleep(5)
            finally:
                if connection and connection.is_open:
                    connection.close()


def main() -> None:
    """CLI entrypoint for disparo worker."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

    rabbitmq_uri = os.getenv("RABBITMQ_URI", "amqp://guest:guest@localhost:5672/")
    worker = DisparoWorker(rabbitmq_uri=rabbitmq_uri, queue_name="leads_disparo")
    worker.run()


if __name__ == "__main__":
    main()
