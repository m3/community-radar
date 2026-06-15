# Multi-Tenant Execution Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a persistent serial execution queue to handle background collection and analysis tasks reliably across multiple tenants.

**Architecture:** A dedicated `data/queue.db` SQLite database stores task state. An `--async` flag in the main CLI enqueues tasks. A standalone `src/queue_worker.py` process executes pending tasks one at a time.

**Tech Stack:** Python, SQLite, Argparse.

---

### Task 1: Task Store Implementation

**Files:**
- Create: `src/db/queue.py`

- [ ] **Step 1: Implement `queue.db` connection and initialization**

```python
import sqlite3
import json
from pathlib import Path
from datetime import datetime

QUEUE_DB_PATH = Path(__file__).parent.parent.parent / "data" / "queue.db"

def get_queue_db():
    QUEUE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(QUEUE_DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            command     TEXT NOT NULL,
            args_json   TEXT,
            status      TEXT DEFAULT 'pending',
            error_log   TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            started_at  TEXT,
            finished_at TEXT
        )
    ''')
    db.commit()
    return db

def enqueue_task(client_name, command, args_dict=None):
    db = get_queue_db()
    args_json = json.dumps(args_dict) if args_dict else None
    db.execute(
        "INSERT INTO tasks (client_name, command, args_json) VALUES (?, ?, ?)",
        (client_name, command, args_json)
    )
    db.commit()
    db.close()
```

- [ ] **Step 2: Commit**

```bash
git add src/db/queue.py
git commit -m "feat(queue): implement task store logic"
```

---

### Task 2: CLI Async Dispatch

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add `--async` global flag**

- [ ] **Step 2: Update CLI dispatcher to intercept enqueued commands**

In `cli()`, if `args.async_mode` is True, instead of calling the function, call `enqueue_task`.

```python
    if getattr(args, "async_mode", False):
        from src.db.queue import enqueue_task
        # Strip internal argparse fields
        task_args = vars(args).copy()
        task_args.pop("async_mode", None)
        task_args.pop("func", None)
        
        enqueue_task(args.client, args.command, task_args)
        print(f"✅ Task '{args.command}' for client '{args.client}' enqueued.")
        return
```

- [ ] **Step 3: Test enqueuing**

Run: `uv run python src/main.py collect --client pure-pool-pro --async`
Expected: "Task 'collect' for client 'pure-pool-pro' enqueued." and a record in `data/queue.db`.

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat(cli): add --async flag for task enqueuing"
```

---

### Task 3: Serial Worker Implementation

**Files:**
- Create: `src/queue_worker.py`

- [ ] **Step 1: Implement the worker loop**

```python
import time
import json
import traceback
import sys
from pathlib import Path

# Ensure imports work
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.db.queue import get_queue_db
from src.main import commands as CLI_COMMANDS

def run_worker():
    print("🚀 CommunityRadar Queue Worker started (Serial Mode)")
    while True:
        db = get_queue_db()
        task = db.execute(
            "SELECT * FROM tasks WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
        ).fetchone()
        
        if not task:
            db.close()
            time.sleep(5)
            continue
            
        task_id = task['id']
        print(f"执行 Task {task_id}: {task['command']} for {task['client_name']}...")
        
        db.execute(
            "UPDATE tasks SET status='running', started_at=datetime('now') WHERE id=?", 
            (task_id,)
        )
        db.commit()
        
        try:
            # Reconstruct args Namespace-like object
            class TaskArgs:
                def __init__(self, d):
                    self.__dict__.update(d)
            
            args_dict = json.loads(task['args_json']) if task['args_json'] else {}
            args_obj = TaskArgs(args_dict)
            
            # Execute the actual CLI function
            func = CLI_COMMANDS[task['command']]
            func(args_obj)
            
            db.execute(
                "UPDATE tasks SET status='completed', finished_at=datetime('now') WHERE id=?", 
                (task_id,)
            )
        except Exception as e:
            err = traceback.format_exc()
            print(f"❌ Task {task_id} failed: {e}")
            db.execute(
                "UPDATE tasks SET status='failed', finished_at=datetime('now'), error_log=? WHERE id=?", 
                (err, task_id)
            )
            
        db.commit()
        db.close()
        time.sleep(2)

if __name__ == "__main__":
    run_worker()
```

- [ ] **Step 2: Commit**

```bash
git add src/queue_worker.py
git commit -m "feat(queue): implement serial background worker"
```

---

### Task 4: Queue Management Commands

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add `queue` subcommand with `status`, `list`, `retry`, and `clear`**

- [ ] **Step 2: Test worker and management**

1. Start worker: `uv run python src/queue_worker.py` (in background)
2. Enqueue task: `uv run python src/main.py collect --client pure-pool-pro --async`
3. Check status: `uv run python src/main.py queue status`
4. Verify data was collected in client DB.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat(cli): add queue management commands"
```
