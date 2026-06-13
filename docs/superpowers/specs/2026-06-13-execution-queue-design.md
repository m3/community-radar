# Design Spec: Multi-Tenant Execution Queue

## Overview
To prevent resource contention (Chrome Bridge bottlenecks) and database write-locks in a multi-tenant environment, Community Radar will implement a persistent execution queue. This system allows for "fire-and-forget" task dispatching via the CLI or API, with a dedicated background worker ensuring tasks are executed reliably one at a time.

## Goals
- **Resource Stability:** Prevent multiple concurrent scrapes from crashing the Reddit Bridge.
- **Data Integrity:** Avoid SQLite `database is locked` errors by serializing writes.
- **Resilience:** Persist tasks to disk so they survive server restarts.
- **API Optimization:** Allow external platforms (superchargedbym3.com) to trigger long-running jobs without blocking.

## Architecture

### 1. Task Store (`data/queue.db`)
A dedicated global SQLite database will track the lifecycle of all background jobs.

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    command     TEXT NOT NULL,    -- e.g., 'collect', 'analyze', 'report'
    args_json   TEXT,             -- Serialized extra arguments
    status      TEXT DEFAULT 'pending', -- pending, running, completed, failed
    error_log   TEXT,             -- Error details if failed
    created_at  TEXT DEFAULT (datetime('now')),
    started_at  TEXT,
    finished_at TEXT
);
```

### 2. Async Dispatch (`--async`)
The main CLI (`src/main.py`) will be updated with a global `--async` flag.

- **Behavior:** If `--async` is present, the command will validate the arguments but *will not* execute the logic. Instead, it will insert a record into `data/queue.db` and exit with a "Task Enqueued" message.
- **Scope:** Applied to `collect`, `export`, `reddit`, `analyze`, and `report`.

### 3. Serial Worker (`src/queue_worker.py`)
A standalone, long-lived Python process that:
1. Polls `data/queue.db` for the oldest `pending` task.
2. Marks the task as `running` and records the start time.
3. Invokes the corresponding function (e.g., `src.main.collect`) within the worker's process context.
4. Updates the status to `completed` or `failed` (with traceback) upon completion.
5. Sleeps briefly and repeats.

### 4. Queue Management CLI
A new `queue` subcommand in `src/main.py`:
- `status`: Show counts of pending/running/failed tasks.
- `list`: List recent tasks and their statuses.
- `retry <id>`: Reset a failed task to `pending`.
- `clear`: Remove completed/failed tasks.

## Key Benefits
- **Deterministic Load:** The server load remains constant regardless of how many clients are added, as only one heavy task runs at a time.
- **Observability:** Easy to track which clients are being processed and why a specific analysis might have failed.
- **Simple Integration:** Minimal changes to existing collector logic; the queue acts as a thin wrapper.

## Security
- **Sanitization:** Reuses the existing client name sanitization from the DB layer.
- **Input Validation:** Only pre-approved commands can be enqueued.
