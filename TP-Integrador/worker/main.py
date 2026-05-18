import pika
import os
import sys
import json
import random

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "admin")
QUEUE_NAME    = "image_queue"
RESULT_QUEUE  = "result_queue"

LABELS = ["Gato", "Mesa", "Silla", "Laptop"]


def analyze_image(image_bytes: bytes) -> list:
    """
    TODO: reemplazar por lógica de IA real.
    Por ahora devuelve probabilidades aleatorias.
    """
    probabilities = [random.uniform(0, 100) for _ in LABELS]
    total = sum(probabilities)

    return [
        {
            "name": label,
            "probability": round((prob / total) * 100, 2)
        }
        for label, prob in zip(LABELS, probabilities)
    ]


def publish_result(channel, results: list):
    channel.queue_declare(queue=RESULT_QUEUE, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=RESULT_QUEUE,
        properties=pika.BasicProperties(delivery_mode=2),
        body=json.dumps(results)
    )
    print(f"Resultado publicado en '{RESULT_QUEUE}': {results}")


def callback(ch, method, properties, body):
    print(f"Mensaje recibido. Tamaño: {len(body)} bytes")
    try:
        results = analyze_image(body)
        print(f"Análisis completado: {results}")

        reply_to = properties.reply_to
        correlation_id = properties.correlation_id
        print(f"  reply_to:       {reply_to}")
        print(f"  correlation_id: {correlation_id}")

        if not reply_to:
            print("ERROR: mensaje sin reply_to, no se puede responder", file=sys.stderr)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        ch.basic_publish(
            exchange="",
            routing_key=reply_to,
            properties=pika.BasicProperties(
                correlation_id=correlation_id,
                delivery_mode=2
            ),
            body=json.dumps(results)
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print("Resultado publicado y mensaje confirmado.")

    except Exception as e:
        print(f"ERROR en callback: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    finally:
        ch.stop_consuming()
        
def main():
    print("=== Worker iniciando ===")
    print(f"  RABBITMQ_HOST: {RABBITMQ_HOST}")
    print(f"  RABBITMQ_PORT: {RABBITMQ_PORT}")
    print(f"  RABBITMQ_USER: {RABBITMQ_USER}")
    print(f"  QUEUE_NAME:    {QUEUE_NAME}")

    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters  = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            connection_attempts=5,
            retry_delay=3,
        )

        print("Conectando a RabbitMQ...")
        connection = pika.BlockingConnection(parameters)
        print("Conexion establecida.")

        channel = connection.channel()
        print("Canal abierto.")

        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        print(f"Cola '{QUEUE_NAME}' declarada.")

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)

        print("Worker esperando mensajes...")
        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError as e:
        print(f"ERROR: No se pudo conectar a RabbitMQ en {RABBITMQ_HOST}:{RABBITMQ_PORT}", file=sys.stderr)
        print(f"  Detalle: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR inesperado: {type(e).__name__}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()