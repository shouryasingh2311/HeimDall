#!/usr/bin/env bash
set -e

echo -e "\033[1;36m==========================================================================\033[0m"
echo -e "\033[1;36m🛡️   Downloading & Launching HeimDall Observability Platform\033[0m"
echo -e "\033[1;36m==========================================================================\033[0m"

DEST_DIR="$HOME/HeimDall"

if [ ! -d "$DEST_DIR" ]; then
    echo "==> Downloading HeimDall from GitHub..."
    TMP_ZIP="/tmp/heimdall-main.zip"
    curl -fsSL -o "$TMP_ZIP" "https://github.com/shouryasingh2311/HeimDall/archive/refs/heads/main.zip"
    echo "==> Extracting files to $DEST_DIR..."
    unzip -q -o "$TMP_ZIP" -d /tmp
    mv /tmp/HeimDall-main "$DEST_DIR"
    rm -f "$TMP_ZIP"
fi

cd "$DEST_DIR"

if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    echo "==> Docker detected! Starting via Docker Compose..."
    docker compose up
else
    echo "==> Starting via Native Launcher..."
    chmod +x start.sh
    ./start.sh
fi
