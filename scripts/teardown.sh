#!/usr/bin/env bash
# teardown.sh – stop and remove all containers, networks, and the named volume.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "╔══════════════════════════════════════════╗"
echo "║   A5 – 3-tier Notes Board  (teardown)    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# -v removes the named volume a5_db_data as well
echo "▶  Stopping and removing containers, networks, and volumes..."
docker compose down -v

echo ""
echo "▶  Verifying nothing is left behind..."
docker ps --filter "name=a5_" --format "table {{.Names}}\t{{.Status}}"
docker network ls --filter "name=a5_" --format "table {{.Name}}\t{{.Driver}}"
docker volume  ls --filter "name=a5_" --format "table {{.Name}}\t{{.Driver}}"

echo ""
echo "Teardown complete. All A5 resources have been removed."
