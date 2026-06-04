# CommunityRadar

Cross-platform community intelligence tool.

Scrapes Discord and Reddit, profiles users across platforms, tracks engagement patterns, and generates actionable insights for business development and community management.

## What It Does

- **Discord export** (DiscordChatExporter) — full channel history, unlimited messages
- **Reddit scraping** (reddit-skills) — posts, comments, scores via your browser session
- **User profiling** — cross-reference users across platforms, engagement scoring, role classification
- **Incremental scans** — only fetches new data since last scan
- **Web dashboard** — query community health, find prospects, generate reports

## Quick Start

```bash
# Setup
uv sync

# Export new Discord data since last scan
python src/main.py export

# Generate HTML report
python src/main.py report

# Launch dashboard
python src/main.py dashboard

# Status
python src/main.py status
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