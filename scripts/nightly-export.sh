#!/bin/bash
# CommunityRadar nightly export wrapper
# Runs Discord + Reddit export, then regenerates the report for all clients.

set -e

PROJECT_DIR="/Users/mathias/Development/Projects/community-radar"
cd "$PROJECT_DIR"

# Ensure we connect to the community-radar Postgres (not m3-postgres)
export DATABASE_URL="postgresql://community_radar:password123@localhost:5432/community_radar"

# Fetch Discord token from BWS (overrides any inherited env var)
export DISCORD_TOKEN=$(bws secret get 70909217-9e02-452b-b933-b45f00c17fee --output json | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")

# Activate venv
source .venv/bin/activate

CLIENTS=("pure-pool-pro" "chess-infinity" "poker-club")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting CommunityRadar export..."

for client in "${CLIENTS[@]}"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Processing client: $client"

    # Run Discord export (incremental)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Discord export for $client..."
    python3 src/main.py -c "$client" export 2>&1 || true

    # Run Reddit export (requires REDDIT_SESSION env var with a logged-in Reddit cookie)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Reddit export for $client..."
    python3 src/main.py -c "$client" reddit 2>&1 || true

    # Regenerate report
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Generating report for $client..."
    python3 src/main.py -c "$client" report 2>&1 || true
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Export complete."
