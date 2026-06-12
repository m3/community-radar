# Multi-Tenant Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition the system to a multi-tenant architecture where each client has its own dedicated database and configuration scope, accessible via a `--client` flag.

**Architecture:** Database-Level Isolation. The `config.yaml` is restructured to group settings by client. The database connection logic is updated to open `data/clients/<client_id>.db`. All CLI commands are updated to require a `--client` identifier.

**Tech Stack:** Python, SQLite, YAML, Argparse.

---

### Task 1: Configuration Restructure

**Files:**
- Modify: `config.yaml`

- [ ] **Step 1: Backup current config and restructure into `clients` format**

```yaml
# Global settings
data_dir: "data"
docs_dir: "docs"
export:
  dce_timeout: 1200
  batch_size: 500

reddit_global:
  skills_dir: "/Users/mathias/Development/Projects/community-radar/scripts"

clients:
  pure-pool-pro:
    name: "Pure Pool Pro"
    reddit:
      subreddits:
        PurePoolPro: { sorts: ["new", "hot", "top?t=month"] }
        billiards: { sorts: ["new", "hot"], track_keywords: ["pure pool"] }
      domain_monitoring:
        enabled: true
        domains: ["purepoolpro.com"]
    discord:
      servers:
        "203428322082816001": ["chat-pure-pool-pro"]
```

- [ ] **Step 2: Commit**

```bash
git add config.yaml
git commit -m "refactor: restructure config for multi-tenancy"
```

---

### Task 3: Update DB Connection Logic

**Files:**
- Modify: `src/db/models.py`

- [ ] **Step 1: Update `get_db()` to accept a client name**

```python
def get_db(client_name=None):
    if client_name:
        db_path = Path(__file__).parent.parent.parent / "data" / "clients" / f"{client_name}.db"
    else:
        # Fallback for now, but should eventually be deprecated
        db_path = Path(__file__).parent.parent.parent / "data" / "community_radar.db"
    
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    # ... existing setup (row_factory, schema init)
```

- [ ] **Step 2: Commit**

```bash
git add src/db/models.py
git commit -m "feat(db): support client-specific database files"
```

---

### Task 4: Enhance CLI with Client Flag

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add `--client` argument to the main parser**

- [ ] **Step 2: Ensure all subcommands pass the `client` name to collectors and analyzers**

- [ ] **Step 3: Update `collect` command to use the client's configuration block**

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat(cli): add mandatory --client flag for multi-tenant support"
```

---

### Task 5: Migrate Collectors to Multi-Tenant

**Files:**
- Modify: `src/collectors/reddit.py`
- Modify: `src/collectors/reddit_domain.py`

- [ ] **Step 1: Update `reddit.py` to accept client name and use scoped config**

- [ ] **Step 2: Update `reddit_domain.py` to accept client name and use scoped config**

- [ ] **Step 3: Verify migration by running for `pure-pool-pro`**

Run: `uv run python src/main.py collect --client pure-pool-pro`
Expected: Data stored in `data/clients/pure-pool-pro.db`.

- [ ] **Step 4: Commit**

```bash
git add src/collectors/reddit.py src/collectors/reddit_domain.py
git commit -m "feat(collectors): migrate Reddit collectors to multi-tenant"
```
