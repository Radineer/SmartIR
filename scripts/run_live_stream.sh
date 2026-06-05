#!/bin/bash
# ==============================================================
# Iris VTuber Live Stream Launcher
# ==============================================================
# Usage: ./scripts/run_live_stream.sh [--setup]
#
# Prerequisites:
#   - aituber-kit submodule initialized
#   - AivisSpeech running (docker compose up aivisspeech)
#   - OBS Studio installed with Browser Source
#
# Architecture:
#   aituber-kit (localhost:3000) -> OBS Browser Source -> YouTube Live
# ==============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
AITUBER_DIR="$PROJECT_ROOT/aituber-kit"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --setup: Initialize aituber-kit submodule and install deps
if [[ "${1:-}" == "--setup" ]]; then
    log_info "Setting up aituber-kit submodule..."

    if [ ! -d "$AITUBER_DIR/.git" ]; then
        cd "$PROJECT_ROOT"
        git submodule add https://github.com/tegnike/aituber-kit.git aituber-kit || true
        git submodule update --init --recursive
    fi

    cd "$AITUBER_DIR"
    log_info "Installing aituber-kit dependencies (npm)..."
    npm install

    # Copy iris.vrm to aituber-kit public directory
    log_info "Copying iris.vrm to aituber-kit..."
    mkdir -p "$AITUBER_DIR/public/vrm"
    cp "$PROJECT_ROOT/frontend/public/models/vrm/iris.vrm" "$AITUBER_DIR/public/vrm/iris.vrm"
    log_info "iris.vrm copied to aituber-kit/public/vrm/"

    # Copy .env if not exists
    if [ ! -f "$AITUBER_DIR/.env" ]; then
        log_info "Creating .env from template..."
        cp "$SCRIPT_DIR/aituber-kit.env.example" "$AITUBER_DIR/.env"
        log_warn "Edit aituber-kit/.env to set your API keys before running."
    fi

    log_info "Setup complete."
    exit 0
fi

# Check prerequisites
if [ ! -d "$AITUBER_DIR/node_modules" ]; then
    log_error "aituber-kit not set up. Run: $0 --setup"
    exit 1
fi

# Ensure iris.vrm is up to date
if [ -f "$PROJECT_ROOT/frontend/public/models/vrm/iris.vrm" ]; then
    mkdir -p "$AITUBER_DIR/public/vrm"
    if [ "$PROJECT_ROOT/frontend/public/models/vrm/iris.vrm" -nt "$AITUBER_DIR/public/vrm/iris.vrm" ] 2>/dev/null; then
        log_info "Updating iris.vrm in aituber-kit..."
        cp "$PROJECT_ROOT/frontend/public/models/vrm/iris.vrm" "$AITUBER_DIR/public/vrm/iris.vrm"
    fi
fi

# Check AivisSpeech
if ! curl -s http://localhost:10101/version > /dev/null 2>&1; then
    log_warn "AivisSpeech not running. Starting via docker compose..."
    cd "$PROJECT_ROOT"
    docker compose up -d aivisspeech
    sleep 5
fi

# Verify AivisSpeech
if curl -s http://localhost:10101/version > /dev/null 2>&1; then
    log_info "AivisSpeech is running"
else
    log_error "AivisSpeech failed to start. Check: docker compose logs aivisspeech"
    exit 1
fi

# Launch aituber-kit
log_info "Starting aituber-kit on http://localhost:3000 ..."
cd "$AITUBER_DIR"
npm run dev &
AITUBER_PID=$!

# Cleanup on exit
cleanup() {
    log_info "Shutting down..."
    kill $AITUBER_PID 2>/dev/null || true
    wait $AITUBER_PID 2>/dev/null || true
}
trap cleanup EXIT

# Wait for aituber-kit to be ready
log_info "Waiting for aituber-kit to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

log_info "============================================"
log_info "Iris VTuber Live Stream Ready!"
log_info "============================================"
log_info ""
log_info "1. Open OBS Studio"
log_info "2. Add Browser Source: http://localhost:3000"
log_info "3. Set YouTube Live stream key in OBS"
log_info "4. Start streaming!"
log_info ""
log_info "Test speech via API:"
log_info '  curl -X POST "http://localhost:3000/api/messages?type=direct_send&clientId=test" \\'
log_info '    -H "Content-Type: application/json" \\'
log_info '    -d '"'"'{"messages":["こんにちは、イリスです！"]}'"'"''
log_info ""
log_info "VRM Model: public/vrm/iris.vrm"
log_info "TTS: AivisSpeech (localhost:10101)"
log_info "Message Receiver: ENABLED"
log_info "============================================"

# Wait for aituber-kit
wait $AITUBER_PID
