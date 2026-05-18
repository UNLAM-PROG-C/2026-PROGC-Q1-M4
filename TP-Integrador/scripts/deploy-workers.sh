#!/usr/bin/env bash
# scripts/deploy-workers.sh

set -euo pipefail

NAMESPACE="tp-integrador"
IMAGE_NAME="tp-integrador-worker:latest"
WORKER_CONTEXT="./worker"
DOCKERFILE="Dockerfile.worker"

K8S_MANIFEST="./k8s/worker-scaledjob.yaml"

# ── 1. Build directo en el namespace k8s.io que usa el cluster ─────────────
echo ">>> [1/3] Construyendo imagen ${IMAGE_NAME}..."
docker build \
  -t "$IMAGE_NAME" \
  -f "$WORKER_CONTEXT/$DOCKERFILE" \
  "$WORKER_CONTEXT"
# Cargar la imagen en el namespace k8s.io que ve el cluster
docker --context desktop-linux save "$IMAGE_NAME" | \
  kubectl run image-loader --image=busybox --rm -i --restart=Never \
  -n default -- sh -c 'cat > /dev/null' 2>/dev/null || true
# Importar via ctr al namespace correcto
docker --context desktop-linux save "$IMAGE_NAME" > /tmp/worker.tar
kubectl cp /tmp/worker.tar kube-system/$(kubectl get pods -n kube-system | grep kube-proxy | head -1 | awk '{print $1}'):/tmp/worker.tar 2>/dev/null || true
echo "    OK."

# ── 2. Namespace ────────────────────────────────────────────────────────────
echo ">>> [2/3] Creando namespace '${NAMESPACE}' (si no existe)..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# ── 3. Manifiestos ──────────────────────────────────────────────────────────
echo ">>> [3/3] Aplicando ${K8S_MANIFEST}..."
kubectl apply -f "$K8S_MANIFEST" -n "$NAMESPACE"

echo ""
echo "Deploy completo. Comandos utiles:"
echo "  kubectl get all -n ${NAMESPACE}"
echo "  kubectl get scaledjob -n ${NAMESPACE}"
echo "  kubectl logs -l app=worker -n ${NAMESPACE} -f"