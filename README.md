# CommunityRadar

Cross-platform community intelligence tool.

Scrapes Discord and Reddit, profiles users across platforms, tracks engagement patterns, and generates actionable insights for business development and community management.

## What It Does

- **Discord export** (DiscordChatExporter) — full channel history, unlimited messages
- **Reddit scraping** (reddit-skills) — posts, comments, scores via your browser session
- **Multi-tenant Dashboard** — dynamic routing and client-specific intelligence
- **Client Management** — browser-based onboarding and form-based configuration editor
- **Execution Queue** — background task processing for large-scale data collection
- **User profiling** — cross-reference users across platforms, engagement scoring, role classification
- **Incremental scans** — only fetches new data since last scan
- **Database Migrations** — automatic schema updates across all tenant databases

## Quick Start

```bash
# Setup
uv sync

# Run database migrations for all clients
python src/main.py migrate

# Launch background task worker (separate terminal)
python src/queue_worker.py

# Launch dashboard
python src/main.py dashboard --client <client_name>
# OR launch the Client Hub to select a client
python src/main.py dashboard
```

## Architecture

```
community-radar/
├── src/
│   ├── collectors/     # Data collection (DCE, reddit-skills)
│   ├── db/             # SQLite schema, queries
│   └── dashboard/      # Web dashboard (Flask)
├── data/               # Exports, state, DB (gitignored)
├── docs/               # Reports, analysis
├── scripts/            # Utility scripts
└── tests/
```

## Data Sources

| Source | Tool | Status |
|--------|------|--------|
| Discord | DiscordChatExporter CLI | ✅ Working |
| Reddit | reddit-skills (Chrome extension) | ✅ Working |
| Reddit | RSS feed (fallback) | ✅ Working |

## Security

- Tokens stored in Bitwarden Secrets Manager (BWS)
- No credentials in config files
- Incremental exports preserve state