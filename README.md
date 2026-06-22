# CommunityRadar

Cross-platform community intelligence tool.

Scrapes Discord and Reddit, profiles users across platforms, tracks engagement patterns, and generates actionable insights for business development and community management.

## What It Does

- **Discord export** (DiscordChatExporter) — full channel history, unlimited messages
- **Reddit scraping** (reddit-skills) — posts, comments, scores via your browser session
- **Data Segmentation** — separate owned (product/support) communities from external (market/hobbyist) channels dynamically to prevent general discussions from muddying direct feedback.
- **Market Awareness** — visualize brand penetration in external subreddits (r/billiards, r/snooker)
- **Heuristic Identity Engine** — automatically map Discord and Reddit users using fuzzy matching
- **Multi-tenant Dashboard** — dynamic routing and client-specific intelligence
- **Client Management** — browser-based onboarding and form-based configuration editor
- **Execution Queue** — background task processing for large-scale data collection
- **User profiling** — engagement scoring, role classification, and cross-platform badges
- **Database Migrations** — automatic schema updates across all tenant databases

## Quick Start

```bash
# Setup
uv sync

# Run database migrations for all clients
python src/main.py migrate

# Map users across platforms (Identity Engine)
python src/main.py --client <client_name> identity

# Launch background task worker (separate terminal)
python src/queue_worker.py

# Launch dashboard
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

## Data Segmentation

The dashboard supports dynamic data segmentation between **Owned (Product/Support)** and **External (Market/Hobbyist)** channels.

### Segmentation Rules:
- **Owned Channels**: Discord servers/channels and subreddits explicitly configured with `owned: true` in `config.yaml` (e.g., `r/PurePoolPro`).
- **External Channels**: All other subreddits (e.g., `r/billiards`, `r/snooker`) and domain monitoring.

### Using Segmentation:
Use the Segment Toggle in the dashboard header to switch views:
- **All Channels**: Combined cross-platform view.
- **Owned (Product)**: Focus on direct player feedback, feature requests, bug reports, and support queries.
- **External (Market)**: High-level market awareness, competitor analysis, and broad industry trends.

Backend REST APIs accept a `?segment=all|owned|external` query parameter to filter all stats, topic rankings, power words, sentiment timeseries, and top contributors in real-time.

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