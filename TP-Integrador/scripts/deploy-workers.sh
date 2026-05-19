#!/usr/bin/env bash
# scripts/deploy-workers.sh

set -euo pipefail

NAMESPACE="tp-integrador"
IMAGE_NAME="francovallejos885/tp-concurrente-worker:v1.0"
WORKER_CONTEXT="./worker"
DOCKERFILE="Dockerfile.worker"
K8S_MANIFEST="./k8s/worker-scaledjob.yaml"

# ── 1. Build ─────────────────────────────────────────────────────────────────
echo ">>> [1/3] Construyendo imagen ${IMAGE_NAME}..."
docker build \
  -t "$IMAGE_NAME" \
  -f "$WORKER_CONTEXT/$DOCKERFILE" \
  "$WORKER_CONTEXT"
echo "    OK."

# ── 2. Push solo si hubo cambios ─────────────────────────────────────────────
echo ">>> [2/3] Verificando si la imagen cambio..."

LOCAL_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE_NAME" 2>/dev/null || echo "none")
REMOTE_DIGEST=$(docker manifest inspect "$IMAGE_NAME" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('config',{}).get('digest','none'))" 2>/dev/null || echo "none")

LOCAL_ID=$(docker inspect --format='{{.Id}}' "$IMAGE_NAME" 2>/dev/null || echo "local_none")
REMOTE_ID=$(docker pull --quiet "$IMAGE_NAME" 2>/dev/null && docker inspect --format='{{.Id}}' "$IMAGE_NAME" 2>/dev/null || echo "remote_none")

if [ "$LOCAL_ID" = "$REMOTE_ID" ]; then
  echo "    Sin cambios, salteando push."
else
  echo "    Cambios detectados, pusheando..."
  docker push "$IMAGE_NAME"
  echo "    OK."
fi

# ── 3. Namespace + manifiesto ────────────────────────────────────────────────
echo ">>> [3/3] Aplicando ${K8S_MANIFEST} en namespace '${NAMESPACE}'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$K8S_MANIFEST" -n "$NAMESPACE"
echo "    OK."

echo ""
echo "Deploy completo. Comandos utiles:"
echo "  kubectl get scaledjob worker -n ${NAMESPACE}"
echo "  kubectl get pods -n ${NAMESPACE} -w"
echo "  kubectl logs -l app=worker -n ${NAMESPACE} --tail=50"