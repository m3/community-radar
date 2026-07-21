#!/usr/bin/env bash
# CommunityRadar deploy wrapper
# Injects secrets from the BWS persona-glenn project, then runs docker compose.
#
# Usage:
#   scripts/deploy.sh                  # docker compose up -d
#   scripts/deploy.sh logs -f          # any docker compose subcommand passes through
#   scripts/deploy.sh down
#
# Requires:
#   - bws CLI on PATH
#   - BWS_ACCESS_TOKEN in .env or exported in the shell (read access to persona-glenn)

set -euo pipefail

# BWS project: persona-glenn
PROJECT_ID="d45b928a-159d-402e-a1a4-b45a00b538d8"

cd "$(dirname "$0")/.."

# Source local .env if present (gitignored)
if [[ -f .env ]]; then
    # shellcheck source=/dev/null
    set -a
    # shellcheck source=/dev/null
    source .env
    set +a
fi

if ! command -v bws >/dev/null 2>&1; then
    echo "ERROR: bws CLI not found on PATH." >&2
    echo "       Install with: brew install bitwarden/tap/bws" >&2
    exit 1
fi

if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
    echo "ERROR: BWS_ACCESS_TOKEN not set." >&2
    echo "       Add it to .env or export it in your shell." >&2
    echo "       Must have decrypt access to the persona-glenn BWS project." >&2
    exit 1
fi

if [[ $# -eq 0 ]]; then
    set -- up -d
fi

echo "Deploying CommunityRadar with secrets from persona-glenn..."
exec bws run --project-id "$PROJECT_ID" -- docker compose "$@"
