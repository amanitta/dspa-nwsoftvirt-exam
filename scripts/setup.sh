#!/usr/bin/env bash
# setup.sh – build images, start all services, and verify the stack is up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."   # run from repo root so compose.yaml is found

echo "╔══════════════════════════════════════════╗"
echo "║   A5 – 3-tier Notes Board  (setup)       ║"
echo "╚══════════════════════════════════════════╝"

# ── 1. Build and start (detached) ─────────────────────────────────────────────
echo ""
echo "▶  Building images and starting containers..."
docker compose up --build -d

# ── 2. Wait until the API health-check passes ─────────────────────────────────
echo ""
echo "▶  Waiting for the API container to be healthy..."
for i in $(seq 1 30); do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' a5_api 2>/dev/null || true)
    if [[ "$STATUS" == "healthy" ]]; then
        echo "   API is healthy."
        break
    fi
    printf "   attempt %d/30: status=%s\n" "$i" "${STATUS:-unknown}"
    sleep 3
done

# ── 3. Quick smoke-test via curl ──────────────────────────────────────────────
echo ""
echo "▶  Smoke-test: GET http://localhost:8080/api/health"
curl -s http://localhost:8080/api/health

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Stack is up!  Open http://localhost:8080 ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Running containers:"
docker compose ps
