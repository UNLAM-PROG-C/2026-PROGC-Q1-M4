import logging
import pika
import os
import sys
import json
import traceback
import numpy as np
from datetime import datetime

from predictor import Predictor

_predictor = None

logger = logging.getLogger(__name__)

TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'


def log(msg: str):
  """Imprime un mensaje con timestamp ISO y flush inmediato."""
  print(f"[{datetime.now().strftime(TIMESTAMP_FORMAT)}] {msg}", flush=True)


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin")
QUEUE_NAME = "image_queue"
DEFAULT_EXCHANGE = ""
DELIVERY_MODE = 2
CONNECTION_ATTEMPTS = 5
RETRY_DELAY = 3
PREFETCH_COUNT = 1

PERCENT_SCALE = 100
PROBABILITY_DECIMALS = 2
FAILED_PROBABILITY = 0.0
EXIT_FAILURE = 1

LABELS = [
  'Remera', 'Pantalon', 'Sueter', 'Vestido', 'Abrigo',
  'Sandalia', 'Camisa', 'Zapatilla', 'Bolso', 'Bota'
]


def _ensure_predictor():
  """Inicializa el Predictor global de forma perezosa y lo devuelve."""
  global _predictor
  if _predictor is None:
    log("[analyze_image] Inicializando Predictor...")
    _predictor = Predictor()
    log("[analyze_image] ✓ Predictor inicializado")
  return _predictor


def _format_probabilities(probabilities) -> list:
  """Convierte el array de probabilidades en la lista de dicts de respuesta."""
  return [
    {"name": LABELS[i], "probability": round(float(prob) * PERCENT_SCALE, PROBABILITY_DECIMALS)}
    for i, prob in enumerate(probabilities)
  ]


def analyze_image(image_bytes: bytes) -> list:
  """Recibe bytes de imagen, ejecuta predicción y devuelve lista formateada.

  Args:
      image_bytes: Bytes de la imagen a analizar.

  Returns:
      Lista de dicts [{"name": str, "probability": float}, ...] con las 10 probabilidades.
  """
  try:
    predictor = _ensure_predictor()
    probabilities = predictor.predict_image(image_bytes)

    predicted_class = int(np.argmax(probabilities))
    confidence = float(probabilities[predicted_class])
    log(f"[analyze_image] Predicción: clase={predicted_class}, confianza={confidence:.2%}")

    return _format_probabilities(probabilities)
  except Exception as e:
    logger.error(f"[analyze_image] ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
    return [{"name": label, "probability": FAILED_PROBABILITY} for label in LABELS]


def _publish_result(ch, reply_to, correlation_id, results):
  """Publica el resultado del análisis en la cola reply_to."""
  ch.basic_publish(
    exchange=DEFAULT_EXCHANGE,
    routing_key=reply_to,
    properties=pika.BasicProperties(
      correlation_id=correlation_id,
      delivery_mode=DELIVERY_MODE
    ),
    body=json.dumps(results)
  )


def _process_message(ch, method, properties, body):
  """Analiza la imagen del mensaje y publica el resultado en su cola reply_to."""
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

  _publish_result(ch, reply_to, correlation_id, results)
  ch.basic_ack(delivery_tag=method.delivery_tag)
  log("Resultado publicado y mensaje confirmado.")


def callback(ch, method, properties, body):
  """Callback de RabbitMQ: analiza la imagen y publica el resultado en reply_to.

  En caso de error, hace nack del mensaje sin reencolar.
  """
  log(f"Mensaje recibido. Tamaño: {len(body)} bytes")
  try:
    _process_message(ch, method, properties, body)
  except Exception as e:
    log(f"ERROR en callback: {type(e).__name__}: {e}")
    traceback.print_exc()
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def _build_connection_parameters():
  """Construye los parámetros de conexión a RabbitMQ desde las variables de entorno."""
  credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
  return pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    credentials=credentials,
    connection_attempts=CONNECTION_ATTEMPTS,
    retry_delay=RETRY_DELAY,
  )


def _start_consuming(parameters):
  """Abre la conexión, declara la cola e inicia el consumo bloqueante de mensajes."""
  log("Conectando a RabbitMQ...")
  connection = pika.BlockingConnection(parameters)
  log("Conexion establecida.")

  channel = connection.channel()
  log("Canal abierto.")

  channel.queue_declare(queue=QUEUE_NAME, durable=True)
  log(f"Cola '{QUEUE_NAME}' declarada.")

  channel.basic_qos(prefetch_count=PREFETCH_COUNT)
  channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

  log("Worker esperando mensajes...")
  channel.start_consuming()


def _log_startup():
  """Registra la configuración con la que arranca el worker."""
  log("=== Worker iniciando ===")
  log(f"  RABBITMQ_HOST: {RABBITMQ_HOST}")
  log(f"  RABBITMQ_PORT: {RABBITMQ_PORT}")
  log(f"  RABBITMQ_USER: {RABBITMQ_USER}")
  log(f"  QUEUE_NAME:    {QUEUE_NAME}")


def main():
  """Configura la conexión a RabbitMQ, declara la cola e inicia el consumo de mensajes."""
  _log_startup()
  try:
    _start_consuming(_build_connection_parameters())
  except pika.exceptions.AMQPConnectionError as e:
    log(f"ERROR: No se pudo conectar a RabbitMQ en {RABBITMQ_HOST}:{RABBITMQ_PORT}")
    log(f"  Detalle: {e}")
    sys.exit(EXIT_FAILURE)
  except Exception as e:
    log(f"ERROR inesperado: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
  main()
