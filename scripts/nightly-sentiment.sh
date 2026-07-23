#!/bin/bash
# CommunityRadar nightly sentiment analysis wrapper
# Runs sentiment analysis for all clients.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Ensure we connect to the community-radar Postgres (not m3-postgres)
export DATABASE_URL="postgresql://community_radar:password123@localhost:5432/community_radar"

# Activate venv
source .venv/bin/activate

# Clients come from config.yaml so this stays in step with the dashboard.
# while-read rather than readarray/mapfile: macOS ships bash 3.2.
CLIENTS=()
while IFS= read -r client; do
    [ -n "$client" ] && CLIENTS+=("$client")
done < <(python3 -c "import yaml; print('\n'.join(yaml.safe_load(open('config.yaml')).get('clients', {})))")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting CommunityRadar sentiment analysis..."

for client in "${CLIENTS[@]}"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Analyzing client: $client"
    PYTHONPATH="$PROJECT_DIR" python3 src/analysis/sentiment.py --client "$client" 2>&1 || true
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sentiment analysis complete."
