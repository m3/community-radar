# Architectural Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address critical gaps from the architectural review by making all CLI commands and the dashboard fully multi-tenant aware, and establishing a foundation for execution queues and migrations.

**Architecture:** Update unscoped CLI commands (`status`, `topics`, `xref`, `search`) to require the `--client` flag. Refactor `src/dashboard/app.py` to accept the `--client` flag, defaulting to a client selection view if none is provided.

**Tech Stack:** Python, Flask, SQLite.

---

### Task 1: Fix CLI Context Leaks

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Update `status` command to require `--client`**

Modify `src/main.py` to enforce `--client` for `status`, `topics`, `xref`, and `search`.

```python
    # Commands that require --client
    client_required_cmds = ["status", "collect", "export", "reddit", "search", "topics", "xref", "analyze", "report"]
    if args.command in client_required_cmds and not args.client:
        config = load_config()
        available = get_available_clients(config)
        print(f"Error: --client is required for '{args.command}'")
        print(f"Available clients: {', '.join(available)}")
        sys.exit(1)
```

- [ ] **Step 2: Update `get_db` calls in unscoped commands**

Update `status`, `topics`, `xref`, and `search` to pass `args.client` to `get_db`.

```python
def status(args):
    # ...
    db = get_db(args.client)
    # ...
```

- [ ] **Step 3: Test modified CLI commands**

Run: `uv run python src/main.py status`
Expected: Error output "Error: --client is required for 'status'"

Run: `uv run python src/main.py status --client pure-pool-pro`
Expected: Status output for `pure-pool-pro`.

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "fix(cli): enforce --client flag for all data access commands"
```

---

### Task 2: Multi-Tenant Dashboard Support

**Files:**
- Modify: `src/dashboard/app.py`
- Modify: `src/dashboard/report.py`

- [ ] **Step 1: Update `app.py` to accept `--client` flag and use it for DB and report paths**

```python
import argparse
from pathlib import Path
from flask import Flask, render_template, abort

# Ensure we can import from src
import sys
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.db.models import get_db

app = Flask(__name__)
CLIENT_NAME = None

@app.route("/")
def index():
    if not CLIENT_NAME:
        return "No client specified. Please run with --client <name>."
    
    db = get_db(CLIENT_NAME)
    # ... fetch data using db ...
    db.close()
    
    report_path = ROOT / "data" / "clients" / CLIENT_NAME / "reports" / "community-sentiment-analysis.json"
    
    # ... render template ...

def run_dashboard(client_name=None):
    global CLIENT_NAME
    CLIENT_NAME = client_name
    app.run(debug=True, port=5000)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--client", help="Client name")
    args = parser.parse_args()
    run_dashboard(args.client)
```

- [ ] **Step 2: Integrate `run_dashboard` in `src/main.py`**

```python
def dashboard(args):
    """Launch web dashboard"""
    if not args.client:
        print("Error: --client is required for 'dashboard'")
        sys.exit(1)
    from src.dashboard.app import run_dashboard
    run_dashboard(args.client)
```

- [ ] **Step 3: Test Dashboard locally**

Run: `uv run python src/main.py dashboard --client pure-pool-pro`
Expected: Flask server starts, navigating to `http://localhost:5000` shows data for `pure-pool-pro`.

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/app.py src/main.py
git commit -m "feat(dashboard): add multi-tenant support to web dashboard"
```