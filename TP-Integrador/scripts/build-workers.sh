#!/usr/bin/env bash
# scripts/push-worker.sh

set -euo pipefail

IMAGE_NAME="francovallejos885/tp-concurrente-worker:v1.0"
WORKER_CONTEXT="./worker"
DOCKERFILE="Dockerfile.worker"

# ── 1. Build ──────────────────────────────────────────────────────────────────
echo ">>> [1/2] Construyendo imagen ${IMAGE_NAME}..."
docker build \
  -t "$IMAGE_NAME" \
  -f "$WORKER_CONTEXT/$DOCKERFILE" \
  "$WORKER_CONTEXT"
echo "    OK."

# ── 2. Push siempre ───────────────────────────────────────────────────────────
echo ">>> [2/2] Pusheando ${IMAGE_NAME} a Docker Hub..."
docker push "$IMAGE_NAME"
echo "    Push completo -> ${IMAGE_NAME}"