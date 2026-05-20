#!/usr/bin/env bash
# scripts/deploy-worker.sh
# Buildea la imagen del worker, la carga al nodo kind y la despliega en K8s.
# No usa Docker Hub — todo es local.
# Uso: bash scripts/deploy-worker.sh
 
set -euo pipefail
 
IMAGE_NAME="tp-integrador-worker:latest"
WORKER_CONTEXT="./worker"
DOCKERFILE="Dockerfile.worker"
NODE="desktop-control-plane"
NAMESPACE="tp-integrador"
K8S_MANIFEST="./k8s/worker-scaledjob.yaml"
 
# ── 1. Build ──────────────────────────────────────────────────────────────────
echo ">>> [1/3] Buildeando imagen ${IMAGE_NAME}..."
docker build \
  -t "$IMAGE_NAME" \
  -f "$WORKER_CONTEXT/$DOCKERFILE" \
  "$WORKER_CONTEXT"
echo "    OK."
 
# ── 2. Cargar al nodo kind ────────────────────────────────────────────────────
echo ">>> [2/3] Cargando imagen al nodo K8s (${NODE})..."
docker save "$IMAGE_NAME" | docker exec -i "$NODE" ctr -n k8s.io images import -
echo "    OK."
 
# ── 3. Namespace + manifiesto ─────────────────────────────────────────────────
echo ">>> [3/3] Desplegando en namespace '${NAMESPACE}'..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f "$K8S_MANIFEST" -n "$NAMESPACE"
echo "    OK."
 
echo ""
echo "Deploy completo."
echo "  kubectl get scaledjob worker -n ${NAMESPACE}"
echo "  kubectl get pods -n ${NAMESPACE} -w"
echo "  kubectl logs -l app=worker -n ${NAMESPACE} --tail=50"
 