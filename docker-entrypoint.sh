#!/bin/bash
set -e

RUNTIME_DIR="${RUNTIME_DIR:-/app/.heimdal/runtime}"
SAAS_PORT="${SAAS_PORT:-8443}"
LOCAL_PORT="${LOCAL_PORT:-9001}"

# Bootstrap runtime credentials, loopback TLS certificates, and tokens if not already generated
if [ ! -f "$RUNTIME_DIR/ca.pem" ] || [ ! -f "$RUNTIME_DIR/saas.json" ]; then
    echo "==> Initializing HeimDall security identities & certificates in $RUNTIME_DIR..."
    python -m scripts.security.bootstrap --runtime "$RUNTIME_DIR" --saas-port "$SAAS_PORT" --local-port "$LOCAL_PORT" --force
fi

# Extract credentials for quick operator access
OPERATOR_TOKEN=$(grep -o '"token": *"[^"]*"' "$RUNTIME_DIR/operator-alpha.json" 2>/dev/null | head -1 | cut -d'"' -f4 || echo "N/A")
COLLECTOR_TOKEN=$(grep -o '"local_token": *"[^"]*"' "$RUNTIME_DIR/collector-alpha.json" 2>/dev/null | head -1 | cut -d'"' -f4 || echo "N/A")

echo ""
echo "=========================================================================="
echo "🛡️   HEIMDALL OBSERVABILITY IS READY"
echo "=========================================================================="
echo "  Operations Dashboard:  https://localhost:${SAAS_PORT}"
echo "  Scenario Verifier:     http://localhost:${LOCAL_PORT}/scenarios"
echo "  Proof / Local Audit:   http://localhost:${LOCAL_PORT}/audit"
echo ""
echo "  Tenant ID:             tenant-alpha"
echo "  Operator Token:        ${OPERATOR_TOKEN}"
echo "  Collector Local Token: ${COLLECTOR_TOKEN}"
echo "=========================================================================="
echo "  Tip: For direct browser dashboard access, enter the Operator Token above."
echo "=========================================================================="
echo ""

# Handle graceful shutdown of background processes
cleanup() {
    echo "==> Shutting down HeimDall services..."
    kill -TERM "$PID_SAAS" "$PID_COLLECTOR" 2>/dev/null || true
    wait "$PID_SAAS" "$PID_COLLECTOR" 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

# 1. Start SaaS backend & static dashboard
python -m backend.saas.main --runtime "$RUNTIME_DIR" --dashboard frontend/dist &
PID_SAAS=$!

# 2. Start Local Collector daemon in scenario mode
python -m backend.collector.daemon --runtime "$RUNTIME_DIR" --scenarios &
PID_COLLECTOR=$!

# Wait for both background processes
wait -n "$PID_SAAS" "$PID_COLLECTOR" || true
cleanup
