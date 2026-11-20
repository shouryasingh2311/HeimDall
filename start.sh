#!/usr/bin/env bash
set -e

echo -e "\033[1;36m==========================================================================\033[0m"
echo -e "\033[1;36m🛡️   Starting HeimDall Observability Platform (Native Unix/macOS)\033[0m"
echo -e "\033[1;36m==========================================================================\033[0m"

# 1. Setup Virtual Environment automatically if missing
if [ ! -d ".venv" ]; then
    echo "==> Creating Python virtual environment in .venv..."
    python3 -m venv .venv
fi

VENV_PYTHON=".venv/bin/python"
VENV_PIP=".venv/bin/pip"

# 2. Install backend dependencies if missing
if [ ! -f ".venv/lib/python"*/site-packages/fastapi/__init__.py ] && [ ! -d ".venv/lib/site-packages/fastapi" ]; then
    echo "==> Installing backend dependencies..."
    $VENV_PIP install -e . --quiet
fi

# 3. Build frontend if missing
if [ ! -f "frontend/dist/index.html" ]; then
    echo "==> Building frontend UI distribution..."
    if command -v npm &> /dev/null; then
        (cd frontend && npm install --silent && npm run build --silent)
    else
        echo "Warning: npm not found in PATH; skipping frontend build."
    fi
fi

# 4. Bootstrap credentials if missing
RUNTIME_DIR=".heimdal/demo"
if [ ! -f "$RUNTIME_DIR/saas.json" ]; then
    echo "==> Bootstrapping TLS certificates and demo tokens in $RUNTIME_DIR..."
    $VENV_PYTHON -m scripts.security.bootstrap --runtime "$RUNTIME_DIR"
fi

OPERATOR_TOKEN=$(grep -o '"token": *"[^"]*"' "$RUNTIME_DIR/operator-alpha.json" | head -1 | cut -d'"' -f4)
COLLECTOR_TOKEN=$(grep -o '"local_token": *"[^"]*"' "$RUNTIME_DIR/collector-alpha.json" | head -1 | cut -d'"' -f4)

echo ""
echo -e "\033[1;32m==========================================================================\033[0m"
echo -e "\033[1;32m🛡️   HEIMDALL IS READY\033[0m"
echo -e "\033[1;32m==========================================================================\033[0m"
echo "  Operations Dashboard:  https://localhost:8443"
echo "  Scenario Verifier:     http://localhost:9001/scenarios"
echo "  Proof / Local Audit:   http://localhost:9001/audit"
echo ""
echo "  Tenant ID:             tenant-alpha"
echo "  Operator Token:        ${OPERATOR_TOKEN}"
echo "  Collector Local Token: ${COLLECTOR_TOKEN}"
echo -e "\033[1;32m==========================================================================\033[0m"
echo "Press Ctrl+C to stop all services."
echo ""

cleanup() {
    echo ""
    echo "==> Stopping HeimDall services..."
    kill -TERM "$PID_SAAS" "$PID_COLLECTOR" 2>/dev/null || true
    wait "$PID_SAAS" "$PID_COLLECTOR" 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

$VENV_PYTHON -m backend.saas.main --runtime "$RUNTIME_DIR" --dashboard frontend/dist &
PID_SAAS=$!

$VENV_PYTHON -m backend.collector.daemon --runtime "$RUNTIME_DIR" --scenarios &
PID_COLLECTOR=$!

wait -n "$PID_SAAS" "$PID_COLLECTOR" || true
cleanup
