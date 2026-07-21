#!/bin/bash
# CommunityRadar nightly sentiment analysis wrapper
# Runs sentiment analysis for all clients.

set -e

PROJECT_DIR="/Users/mathias/Development/Projects/community-radar"
cd "$PROJECT_DIR"

# Ensure we connect to the community-radar Postgres (not m3-postgres)
export DATABASE_URL="postgresql://community_radar:password123@localhost:5432/community_radar"

# Activate venv
source .venv/bin/activate

CLIENTS=("pure-pool-pro" "chess-infinity" "poker-club")

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting CommunityRadar sentiment analysis..."

for client in "${CLIENTS[@]}"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Analyzing client: $client"
    PYTHONPATH="$PROJECT_DIR" python3 src/analysis/sentiment.py --client "$client" 2>&1 || true
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sentiment analysis complete."
