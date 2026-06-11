#!/bin/bash
# CommunityRadar nightly export wrapper
# Runs Discord + Reddit export, then regenerates the report

set -e

PROJECT_DIR="/Users/mathias/Development/Projects/community-radar"
cd "$PROJECT_DIR"

# Activate venv
source .venv/bin/activate

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting CommunityRadar export..."

# Run Discord export (incremental)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Discord export..."
python3 src/main.py export 2>&1

# Run Reddit export
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Reddit export..."
python3 src/main.py reddit 2>&1

# Regenerate report
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Generating report..."
python3 src/main.py report 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Export complete."
