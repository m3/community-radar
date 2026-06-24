# CommunityRadar

Cross-platform community intelligence tool.

Scrapes Discord and Reddit, profiles users across platforms, tracks engagement patterns, and generates actionable insights for business development and community management.

## What It Does

- **Discord export** (DiscordChatExporter) — full channel history, unlimited messages
- **Reddit scraping** (reddit-skills) — posts, comments, scores via your browser session
- **Data Segmentation** — separate owned (product/support) communities from external (market/hobbyist) channels dynamically
- **Market Awareness** — visualize brand penetration in external subreddits (r/billiards, r/snooker)
- **Heuristic Identity Engine** — automatically map Discord and Reddit users using fuzzy matching
- **Multi-tenant Dashboard** — dynamic routing and client-specific intelligence
- **Client Management** — browser-based onboarding and form-based configuration editor
- **Execution Queue** — background task processing for large-scale data collection
- **User profiling** — engagement scoring, role classification, and cross-platform badges
- **Database Migrations** — Alembic-based schema updates (PostgreSQL)

## Quick Start (Local)

```bash
# Setup
uv sync

# Run database migrations
python src/main.py migrate

# Map users across platforms (Identity Engine)
python src/main.py --client <client_name> identity

# Launch background task worker (separate terminal)
python src/queue_worker.py

# Launch dashboard
python src/main.py dashboard
```

## Quick Start (Docker)

```bash
# Start full stack (Postgres + Flask backend + queue worker)
docker compose up -d --build

# Access dashboard
open http://127.0.0.1:5001/pure-pool-pro/intel

# View logs
docker compose logs -f backend worker

# Stop
docker compose down
```

### Docker Services

| Service | Port | Description |
|---------|------|-------------|
| db | 5432 | PostgreSQL 15 |
| backend | 5001 | Flask dashboard + API |
| worker | — | Background queue processor |

### Docker Volumes

- `pgdata` — PostgreSQL data (persists across restarts)
- `./data` bind-mounted to `/app/data` in backend and worker (reports, exports, config)

## Architecture

```
community-radar/
├── src/
│   ├── collectors/     # Data collection (DCE, reddit-skills)
│   ├── db/             # SQLAlchemy ORM, migrations (PostgreSQL)
│   ├── analysis/       # Sentiment analysis, competitor intel
│   ├── dashboard/      # Flask web dashboard + REST API
│   └── queue_worker.py # Background task processor
├── data/               # Exports, reports, client data (gitignored)
├── docs/               # Analysis reports, sentiment reports
├── scripts/            # Utility scripts (migration, etc.)
├── tests/              # Test suite
├── Dockerfile          # Python backend/worker image
└── docker-compose.yml  # Full stack definition
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

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/<client>/overview` | Summary stats (messages, users, channels) |
| `/api/<client>/sentiment/timeseries` | Daily sentiment trends by platform |
| `/api/<client>/sentiment/topics` | Topic-level sentiment rankings |
| `/api/<client>/contributors` | Top contributors by engagement |
| `/api/<client>/negative_messages` | Most negative messages |
| `/api/<client>/channels` | Channel list with stats |
| `/api/<client>/power_words` | Community-specific power words |
| `/api/<client>/market/awareness` | Brand penetration in external channels |
| `/api/queue/status` | Execution queue status |

## Security

- Tokens stored in Bitwarden Secrets Manager (BWS)
- No credentials in config files
- All Docker ports bound to `127.0.0.1` only
- PostgreSQL password authentication (not exposed to internet)
