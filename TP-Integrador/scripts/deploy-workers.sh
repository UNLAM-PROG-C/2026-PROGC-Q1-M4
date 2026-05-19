#!/usr/bin/env bash
# scripts/deploy-workers.sh
# Uso: bash scripts/deploy-workers.sh
# Despliega el worker en K8s usando la imagen ya publicada en Docker Hub.
# Para actualizar la imagen primero correr: bash scripts/push-worker.sh

set -euo pipefail

NAMESPACE="tp-integrador"
K8S_MANIFEST="./k8s/worker-scaledjob.yaml"

# ── 1. Namespace ──────────────────────────────────────────────────────────────
echo ">>> [1/2] Creando namespace '${NAMESPACE}' (si no existe)..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
echo "    OK."

# ── 2. Manifiesto ─────────────────────────────────────────────────────────────
echo ">>> [2/2] Aplicando ${K8S_MANIFEST} en namespace '${NAMESPACE}'..."
kubectl apply -f "$K8S_MANIFEST" -n "$NAMESPACE"
echo "    OK."

echo ""
echo "Deploy completo. Comandos utiles:"
echo "  kubectl get scaledjob worker -n ${NAMESPACE}"
echo "  kubectl get pods -n ${NAMESPACE} -w"
echo "  kubectl logs -l app=worker -n ${NAMESPACE} --tail=50"