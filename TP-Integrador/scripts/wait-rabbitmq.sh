#!/usr/bin/env bash
# scripts/wait-rabbitmq.sh
# Espera hasta que RabbitMQ responda en localhost:15672 antes de desplegar workers.
# KEDA intenta conectarse a la cola al momento de aplicar el ScaledJob,
# así que si RabbitMQ no está listo el trigger queda en error.
 
set -euo pipefail
 
HOST="localhost"
PORT="15672"
MAX_ATTEMPTS=30
SLEEP_SECONDS=3
 
echo "Esperando RabbitMQ en ${HOST}:${PORT}..."
 
for i in $(seq 1 $MAX_ATTEMPTS); do
  if curl -s -o /dev/null -u admin:admin "http://${HOST}:${PORT}/api/overview"; then
    echo "RabbitMQ listo (intento ${i}/${MAX_ATTEMPTS})"
    exit 0
  fi
  echo "  [${i}/${MAX_ATTEMPTS}] No responde aun... reintentando en ${SLEEP_SECONDS}s"
  sleep "$SLEEP_SECONDS"
done
 
echo ""
echo "ERROR: RabbitMQ no levanto en $((MAX_ATTEMPTS * SLEEP_SECONDS))s"
echo "Revisa con: docker compose logs rabbitmq"
exit 1
 