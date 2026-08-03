# Community Radar — Project Contract (LOCAL)

Local rules for this repo. Global behavioral policy is NOT inlined here; it is fetched at
boot and signed (hash + nonce). This file is the local map only.

rules: mcp://localhost:8888/mcp/hermes/rules@1

## What this is
Cross-platform community intelligence tool that scrapes Discord (DiscordChatExporter) and Reddit (reddit-skills), profiles users across platforms, and generates insights for business development and community management (README.md:3-5). Python (>=3.11) + Flask + SQLAlchemy/PostgreSQL, with a multi-tenant dashboard (pyproject.toml:1-17; README.md:74-77).

## Non-negotiable (local)
- Segmentation of **Owned** vs **External** channels is driven by `owned: true` per subreddit/Discord channel in `config.yaml` — never hardcoded (README.md:90-92; `config.yaml` `pure-pool-pro.reddit.subreddits.PurePoolPro.owned: true`).
- **RLS is the sole tenant guard.** All queries go through the `radar_app` non-superuser runtime engine; RLS fails closed to zero rows (src/db/models.py:216-223; covered by tests/test_rls.py). Do not add a bypass path.
- No credentials in config files: tokens live in Bitwarden Secrets Manager (BWS); all Docker ports bind to `127.0.0.1` only; PostgreSQL uses password auth and is not exposed to the internet (README.md:125-128).
- Schema changes go through Alembic migrations targeting PostgreSQL (README.md:18; pyproject.toml `alembic` dependency).

## Commands
No package.json (Python project). From README.md:
- `uv sync` — setup
- `python src/main.py migrate` — run DB migrations
- `python src/main.py dashboard` — launch dashboard
- `python src/main.py --client <client_name> identity` — Identity Engine user mapping
- `python src/queue_worker.py` — background task worker
- `docker compose up -d --build` / `docker compose logs -f backend worker` / `docker compose down` — full stack (Postgres + backend + worker)

## Code graph
The repo is indexed in `.mex/graph.db`. First action on a task: `mex graph scope "<task>"`.
Never naive-grep the whole tree; expand nodes with `mex graph get <id> --detail source` and
check impact with `mex impact <symbol|file>`.

## Navigation
At session start read `.mex/ROUTER.md` + relevant `.mex/context/*` before acting. Update the
vault project card (10-Projects/Community Radar.md) when status/architecture changes.
