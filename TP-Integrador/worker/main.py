import logging
import pika
import os
import sys
import json
import numpy as np
from datetime import datetime

from predictor import Predictor

_predictor = None

logger = logging.getLogger(__name__)


def log(msg: str):
    """Imprime un mensaje con timestamp ISO y flush inmediato."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin")
QUEUE_NAME = "image_queue"
DELIVERY_MODE = 2
CONNECTION_ATTEMPTS = 5
RETRY_DELAY = 3

LABELS = [
    'Remera', 'Pantalon', 'Sueter', 'Vestido', 'Abrigo',
    'Sandalia', 'Camisa', 'Zapatilla', 'Bolso', 'Bota'
]


def analyze_image(image_bytes: bytes) -> list:
    """Recibe bytes de imagen, ejecuta predicción y devuelve lista formateada.

    Args:
        image_bytes: Bytes de la imagen a analizar.

    Returns:
        Lista de dicts [{"name": str, "probability": float}, ...] con las 10 probabilidades.
    """
    global _predictor

    try:
        if _predictor is None:
            log("[analyze_image] Inicializando Predictor...")
            _predictor = Predictor()
            log("[analyze_image] ✓ Predictor inicializado")

        probabilities = _predictor.predict_image(image_bytes)

        predicted_class = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_class])
        log(f"[analyze_image] Predicción: clase={predicted_class}, confianza={confidence:.2%}")

        return [
            {"name": LABELS[i], "probability": round(float(prob) * 100, 2)}
            for i, prob in enumerate(probabilities)
        ]

    except Exception as e:
        logger.error(f"[analyze_image] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return [{"name": label, "probability": 0.0} for label in LABELS]


def callback(ch, method, properties, body):
    """Callback de RabbitMQ: analiza la imagen y publica el resultado en reply_to.

    Lee la imagen desde el cuerpo del mensaje, llama a analyze_image y
    responde por la cola reply_to con el correlation_id correspondiente.
    En caso de error, hace nack del mensaje sin reencolar.
    """
    log(f"Mensaje recibido. Tamaño: {len(body)} bytes")
    try:
        results = analyze_image(body)
        log(f"Análisis completado: {results}")

        reply_to = properties.reply_to
        correlation_id = properties.correlation_id
        log(f"  reply_to:       {reply_to}")
        log(f"  correlation_id: {correlation_id}")

        if not reply_to:
            log("ERROR: mensaje sin reply_to, no se puede responder")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        ch.basic_publish(
            exchange="",
            routing_key=reply_to,
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                delivery_mode=DELIVERY_MODE
            ),
            body=json.dumps(results)
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log("Resultado publicado y mensaje confirmado.")

    except Exception as e:
        log(f"ERROR en callback: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        #ch.stop_consuming()
        pass


def main():
    """Configura la conexión a RabbitMQ, declara la cola e inicia el consumo de mensajes."""
    log("=== Worker iniciando ===")
    log(f"  RABBITMQ_HOST: {RABBITMQ_HOST}")
    log(f"  RABBITMQ_PORT: {RABBITMQ_PORT}")
    log(f"  RABBITMQ_USER: {RABBITMQ_USER}")
    log(f"  QUEUE_NAME:    {QUEUE_NAME}")

    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters  = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            connection_attempts=CONNECTION_ATTEMPTS,
            retry_delay=RETRY_DELAY,
        )

        log("Conectando a RabbitMQ...")
        connection = pika.BlockingConnection(parameters)
        log("Conexion establecida.")

        channel = connection.channel()
        log("Canal abierto.")

        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        log(f"Cola '{QUEUE_NAME}' declarada.")

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

        log("Worker esperando mensajes...")
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        log(f"ERROR: No se pudo conectar a RabbitMQ en {RABBITMQ_HOST}:{RABBITMQ_PORT}")
        log(f"  Detalle: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"ERROR inesperado: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()