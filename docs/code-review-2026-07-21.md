# CommunityRadar — Project Review

*2026-07-21 · reviewed at commit `dcee0a5` plus the uncommitted working tree (15 files, +657/−141)*

## Summary

The product shape is good: a multi-tenant collector → Postgres → Flask dashboard pipeline
with a real task queue, alembic migrations, pydantic config validation, and a 30-test suite.
The uncommitted work (de-hardcoding "Pure Pool" into per-client `brand_keywords`, env-var
secret injection, BWS deploy wrapper) is moving in the right direction.

The problems are concentrated in three places: **nothing creates the database schema**,
**the dashboard has no authentication and runs the Werkzeug debugger**, and **tenant isolation
is implemented by regex-rewriting SQL strings at runtime**. Everything else is tail.

---

> **Status update — findings #1, #2, #3 (partly), #6, #7 are fixed on branch
> `fix/review-2026-07-21`.** Fixing them surfaced two further defects that were
> not visible from reading the code; both are recorded as #13 and #14 below and
> are also fixed. Remaining open: #3b (auth), #4, #5, #8–#12, #15.

## Critical

### 1. Nothing ever creates the schema — a fresh deploy cannot work

`src/db/session.py:17` defines `init_db()`. Nothing calls it. Nothing runs alembic either:

```
$ git grep -n "init_db\|create_all\|alembic upgrade" -- src/ scripts/ Dockerfile docker-compose.yml
src/db/migrate.py:6:def apply_migrations(db: sqlite3.Connection):   # dead SQLite code
```

`Dockerfile` and `docker-compose.yml` go straight to `python -m src.main dashboard` /
`python src/queue_worker.py`. On a clean volume, `docker compose up` gives you an empty
database and every query raises `UndefinedTable`. The existing deployment only works because
its Postgres volume was populated out-of-band (`scripts/migrate_sqlite_to_pg.py`).

**Worse, the command that claims to fix this is a no-op.** `src/main.py:191-203`:

```python
def migrate_dbs(args):
    # get_db automatically applies migrations
    db = get_db(client)      # ← it does not; it opens a session and creates a Client row
    db.close()
    print(f"✅ {client} migration complete.")
```

`get_db` (`src/db/models.py:182`) applies no migrations. The command prints success while
doing nothing.

**Fix:** add `alembic upgrade head` to container startup (entrypoint or a one-shot
`migrate` service in compose) and rewrite `migrate_dbs` to shell out to alembic.

### 2. Three competing schema mechanisms, two of them dead

| Mechanism | State |
|---|---|
| `migrations_pg/versions/*` (alembic, 3 revisions) | The real one — never executed |
| `src/db/migrations/001_initial_schema.sql` | SQLite-era, orphaned |
| `src/db/migrate.py` | SQLite-era — `import sqlite3`, `executescript`, `datetime('now')`. Dead. |

`src/db/migrate.py` is also covered by `tests/test_migrate.py`, so ~70 lines of the suite
test code that can never run against the actual Postgres backend. Delete both SQLite
artifacts and their test; keep alembic as the single source of truth.

### 3. No authentication anywhere + `debug=True` in the production path

`src/dashboard/app.py:1476`:

```python
def run_dashboard(client_name=None):
    app.run(host="0.0.0.0", port=5001, debug=True)
```

`main.py:185` → `docker-compose.yml` `command: ["python", "-m", "src.main", "dashboard"]`.
This is the container's entrypoint, so **the deployed backend runs in debug mode**: any
unhandled exception returns a full traceback with surrounding source and local variables to
the caller, the auto-reloader runs in production, and the interactive debugger console is
exposed (PIN-gated by Werkzeug 3, so not directly RCE — but the PIN is derived from
predictable host data and the traceback disclosure alone is disqualifying). Also
`client_name` is accepted and ignored.

There is no auth layer at all: every `/api/<client_name>/*` route is reachable by anyone who
can hit the port, including `POST /api/<client>/trigger/<command>` which enqueues background
work. The `csrf_protect`/`set_csrf_cookie` pair (`app.py:133-151`) is a double-submit cookie
guarding routes that have no identity behind them.

Currently mitigated only by `ports: "127.0.0.1:5001:5001"`. That's one compose edit or one
reverse proxy away from full exposure, and the tool is explicitly multi-tenant (three clients
in `config.yaml`) — tenant A's operator can read tenant B's data by editing the URL.

**Fix, in order:** (a) `debug=False`, run under gunicorn/waitress; (b) put auth in front of
everything — even HTTP basic via the proxy beats nothing; (c) scope sessions to a client.

Also: `set_csrf_cookie` sets no `Secure` flag, and both CSRF hooks short-circuit entirely
when `app.config["TESTING"]` — so the test suite exercises a different security posture than
production.

---

## High

### 4. Tenant isolation depends on regex string-rewriting of SQL

`LegacySessionWrapper.execute` (`src/db/models.py:29-98`) rewrites every SQL string at
runtime to inject `client_id`. I traced the call sites and **I did not find a query that
currently leaks cross-tenant rows** — but the mechanism is one refactor away from silently
doing so, with no test that would catch it. Three specific fragilities:

- **`models.py:53`** — `elif ":client_id" in sql or "client_id" in sql.lower():` — *any*
  query that merely mentions the string `client_id` anywhere (a SELECT-list column, a
  `GROUP BY`, a comment) is assumed to already filter by tenant. Only the bind param is
  added; **no WHERE clause is injected**. Write `SELECT client_id, COUNT(*) FROM messages
  GROUP BY client_id` and you get every tenant's data, silently.
- **`models.py:59`** — the alias regex `\bFROM\s+\w+\s+(?:AS\s+)?(\w+)` captures SQL keywords
  as aliases. `FROM messages GROUP BY platform` yields alias `GROUP`. Harmless today only
  because that query has no JOIN; add one and it emits `GROUP.client_id = 3`.
- **`models.py:49,108`** — the "tasks table is global" escape hatch is a substring test.
  Any statement containing the substring `tasks` (a column name, a literal value) skips
  tenant injection entirely.

`models.py:70` also interpolates `client_id` directly into the string rather than binding it.
It's an int from the DB so it isn't injectable, but it's the wrong reflex in the one function
that guards tenant boundaries.

**Direction:** the ORM already has the right shape — composite `(id, client_id)` PKs and
`ForeignKeyConstraint`s in `orm.py`. Move the hot paths to SQLAlchemy `select()` with
`with_loader_criteria`, or set a Postgres session variable + row-level security policies and
let the database enforce it. Until then, add a test that asserts every wrapper-rewritten
query emits a tenant predicate.

### 5. `get_db` silently creates tenants

`src/db/models.py:188-195` — if the client row doesn't exist, it's created on the spot.
The HTTP routes are protected by `validate_client()`, but collectors, the worker, and the CLI
all reach `get_db` directly. A typo in a config key or a CLI flag creates a new empty tenant
instead of erroring. Make it raise; add explicit client creation to the `POST /api/clients`
path only.

### 6. `db.rollback()` doesn't exist — worker error handling crashes

`LegacySessionWrapper` implements `execute`, `executemany`, `commit`, `close`. No `rollback`.
`src/queue_worker.py:35, 91, 136` call `db.rollback()` where `db = get_queue_db()` — a
`LegacySessionWrapper`. All three are in `except` blocks, so a task failure raises
`AttributeError` *inside the handler that was supposed to record the failure* — the task stays
`running`, the heartbeat thread has already been asked to stop, and the worker loop dies.
Add `def rollback(self): self.session.rollback()`.

(The `session.rollback()` calls at `queue_worker.py:61, 68` are fine — those go to the real
SQLAlchemy `Session`.)

`queue_worker.py:91` also has `except (DBAPIError, Exception)`, which is just `except Exception`.

---

## Medium

### 7. The test suite doesn't run

```
$ uv run pytest -q
E   ModuleNotFoundError: No module named 'src'      × 11 modules
$ PYTHONPATH=. uv run pytest -q
1 failed, 29 passed
```

No `conftest.py`, no `[tool.pytest.ini_options]`. Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

The failure is `tests/test_reddit_domain.py::test_build_domain_json_url` — the uncommitted
change swapped `reddit.com/domain/<d>/new.json` for `reddit.com/search.json?q=site:<d>`
without updating the assertion. Update the test before committing.

### 8. Per-request full table scans with in-Python sentiment classification

`api_sentiment_timeseries` (`app.py:299`), `api_topics`, `api_power_words`, `api_purpose`
all do: `SELECT content FROM messages` with no limit → loop in Python → `classify_sentiment`
per row. `api_topics` is worse — it's O(messages × topics) with a substring test per pair.
Latency grows linearly with corpus size on every page load, and the work is identical between
requests.

The precomputed `community-sentiment-analysis.json` report already exists and is used for
`segment=all`. Extend the nightly job to precompute the `owned`/`external` segments too, or
persist a `sentiment_label` column at ingest and let Postgres do the `GROUP BY`.

### 9. `ConfigManager` caches forever, across processes

`src/dashboard/config_manager.py:12` — `self._cache` is populated once and never invalidated
by mtime. `clear_cache()` exists but has no caller. The web process and the worker process
hold independent caches, so a config edit through the UI is invisible to the worker until it
restarts, and vice versa. Stat the file and reload on mtime change.

`save()` also only ever writes `config.yaml.bak` once (`if not self.backup_path.exists()`),
so the "backup" is frozen at whatever the config looked like the first time it was edited —
and `config.yaml.bak` is committed to the repo.

### 10. `app.py` is 1478 lines with the same 12-line block copy-pasted eight times

This segment filter:

```python
if segment == "owned":
    if owned_ids:
        query += " AND m.channel_id IN (" + ", ".join("?" for _ in owned_ids) + ")"
        params.extend(owned_ids)
    else:
        query += " AND 1=0"
elif segment == "external":
    ...
```

appears at `app.py:209, 314, 467, 526, 571, 636, 720, 928`. Extract
`apply_segment_filter(query, params, segment, owned_ids, external_ids)`. The
"load config → extract `owned_subreddits`" preamble is duplicated six more times
(`app.py:355, 383, 411, 667, 690`) and should be one helper.

Splitting the module into blueprints (`intel`, `engagement`, `clients`, `queue`) would
follow naturally.

### 11. Unvalidated int coercion → 500s

`app.py:910-911` and `1252` — `int(request.args.get("limit", 100))` raises `ValueError` on
`?limit=abc`, producing an unhandled 500. There's no error handler registered, so with
`debug=True` that renders a stack trace. Coerce defensively and register 400/500 handlers.

### 12. Two CLI commands are broken under Postgres

`main.py:75` — `r['first_seen'][:10]` and `main.py:173` — `r['timestamp'][:19]`. Under SQLite
these were TEXT; `orm.py` now maps them to `DateTime`, so psycopg returns `datetime` objects
and both slices raise `TypeError`. `main.py topics` and `main.py search` are dead. (The web
paths at `app.py:338` handle both types correctly — port that pattern.)

---

---

## Found while fixing (not visible from reading the code)

### 13. Clients sharing a subreddit silently lost data — FIXED

The live database carried `UNIQUE (message_id)` on `messages`, **global across
every tenant**. The collectors emit `INSERT OR IGNORE`, which the wrapper turns
into `ON CONFLICT ... DO NOTHING` — so when a second client tried to store a post
another client already had, it lost the row *with no error*.

Live evidence: `chess-infinity` and `poker-club` both track `r/pcgaming`
(`config.yaml`). `chess-infinity` has 673 messages there. `poker-club` has both
channel rows — `reddit-pcgaming-hot`, `reddit-pcgaming-new` — and **zero
messages**.

Fixed by `UNIQUE (client_id, message_id)` (migration `096a7e1d662f`).

**The already-lost messages do not come back on their own.** Recovering
`poker-club`'s r/pcgaming history means re-running collection, which re-scrapes
Reddit — a live, outward-facing action, so it is deliberately not part of the fix.

### 14. Databases built from alembic head could not accept any message — FIXED

The ORM declared no unique constraint on `messages` at all, so a database
created from head had nothing matching the collectors' `ON CONFLICT (message_id)`
target. Every collector insert failed:

```
psycopg2.errors.InvalidColumnReference: there is no unique or exclusion
constraint matching the ON CONFLICT specification
```

Only the live database worked, because its constraint came from the SQLite
import rather than from a migration. Fixing #1 made fresh deploys build a
schema; this is what made that schema usable. Same fix as #13.

### 15. Finding #4 is no longer latent — demonstrated

While testing #13 I ran, through the wrapper:

```sql
SELECT client_id, message_id FROM messages WHERE message_id = ?
```

It returned rows belonging to **two different tenants**. This is exactly the
`models.py:53` escape hatch: the statement mentions `client_id` in the SELECT
list, so the wrapper assumed it was already tenant-filtered and injected no
`WHERE` clause. No cross-tenant query is needed to trigger it — merely
*selecting* the column is enough.

This moves #4 from "fragile, works today" to "reachable by ordinary code".
Still unfixed — it needs the ORM/RLS migration described there, not a patch.

Related: `_fix_insert_or_ignore`'s regex uses `[^)]+` for the VALUES list, so any
function call in VALUES (`NOW()`, `COALESCE(...)`) truncates the match and emits
a syntax error. Today's collectors pass bare placeholders, so nothing hits it.

---

## Low / hygiene

- **The `clients` table has 10 rows; `config.yaml` defines 3.** Concrete
  confirmation of #5: `client_a`, `client_b`, `test_client`, `reddit-r-billiards`,
  `reddit-r-snooker`, `chess-ultra` and `pure_pool_pro` were all auto-created by
  `get_db`, all with zero messages. Note `pure_pool_pro` alongside the real
  `pure-pool-pro` — a hyphen/underscore typo silently created a tenant rather
  than erroring.
- **Machine-specific absolute paths in tracked files.** `config.yaml:8` `skills_dir:
  /Users/mathias/...`, `config.yaml:12` `dce_bin: /Users/mathias/.hermes/...`,
  `scripts/nightly-sentiment.sh:7` `PROJECT_DIR=/Users/mathias/...`. None of these resolve
  inside the container. Make them env-overridable.
- **`nightly-sentiment.sh` hardcodes the client list** (`pure-pool-pro`, `chess-infinity`,
  `poker-club`) and the DB password, duplicating `config.yaml`. Read clients from config.
- **`Dockerfile` ignores `uv.lock`** — `pip install -e .` resolves fresh against the loose
  ranges in `pyproject.toml` (`flask>=3.0`, `sqlalchemy>=2.0.51`). Builds are not
  reproducible. Use `uv sync --frozen`. It also doesn't `COPY` `migrations_pg/`, which
  blocks the fix for finding #1.
- **`password123` in `docker-compose.yml`, `.env.example`, `session.py:10`,
  `nightly-sentiment.sh`.** Fine for a localhost-bound dev DB, but it's now in four places
  and one of them is the default in application code. The BWS wiring in `scripts/deploy.sh`
  is the right pattern — extend it to `POSTGRES_PASSWORD`.
- **`datetime.utcnow()` deprecated** — 5 warnings from `queue_worker.py`/`tests`. Use
  `datetime.now(timezone.utc)`.
- **`import json` / `import re` / `import os` repeated inside function bodies** throughout
  `app.py` and `models.py` (e.g. `app.py:1225`, `models.py:102,138`). Hoist to module level.
- **657 uncommitted lines sitting on `main`.** Branch this work; the failing test would have
  been caught by a pre-push run.

---

## Suggested order

1. `pythonpath` in `pyproject.toml`, fix `test_reddit_domain`, commit the working tree to a branch (#7)
2. `debug=False` + a real WSGI server (#3a)
3. Wire `alembic upgrade head` into startup; delete the two dead SQLite schema paths (#1, #2)
4. Add `rollback()` to `LegacySessionWrapper` (#6)
5. Auth in front of the dashboard (#3b)
6. Extract the segment-filter helper; split `app.py` into blueprints (#10)
7. Plan the migration off regex SQL rewriting onto ORM-level or RLS tenant scoping (#4)
