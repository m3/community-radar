# Dynamic Tenant Routing & Client Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the single-tenant dashboard into a multi-tenant web portal with dynamic routing and a client hub.

**Architecture:** Use URL-prefixed routes `/<client_name>/...` to determine tenancy. Load available clients from `config.yaml`. Implement a base `layout.html` with a sidebar for shared UI elements.

**Tech Stack:** Flask, Jinja2, Chart.js, SQLite.

---

### Task 1: Refactor `app.py` Utilities

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Add `load_config` helper**

```python
import yaml

def load_config():
    """Load configuration from config.yaml."""
    config_path = ROOT / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 2: Refactor `get_db` and `load_report` to accept `client_name`**

```python
def get_db(client_name):
    """Get database connection for a specific client."""
    return _get_db(client_name)

def load_report(client_name):
    """Load latest sentiment analysis report for a specific client."""
    report_path = ROOT / "data" / "clients" / client_name / "reports" / "community-sentiment-analysis.json"
    if report_path.exists():
        with open(report_path) as f:
            return json.load(f)
    return {}
```

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/app.py
git commit -m "refactor(web): update app utilities for multi-tenancy"
```

### Task 2: Implement Hub and Index Routes

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Add Hub route and update Index route**

```python
@app.route("/")
def hub():
    """Client selection hub."""
    config = load_config()
    clients = config.get("clients", {})
    return render_template("hub.html", clients=clients)

@app.route("/<client_name>/dashboard")
def index(client_name):
    """Main dashboard page for a specific client."""
    config = load_config()
    if client_name not in config.get("clients", {}):
        from flask import abort
        abort(404)
        
    report = load_report(client_name)
    return render_template("index.html", client_name=client_name, report=report)
```

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/app.py
git commit -m "feat(web): add client hub and dynamic dashboard routing"
```

### Task 3: Prefix API Routes

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Update all API routes to include `<client_name>`**
Example for `api_overview`:
```python
@app.route("/api/<client_name>/overview")
def api_overview(client_name):
    """High-level stats for dashboard cards."""
    db = get_db(client_name)
    # ... rest of function ...
```
Do this for:
- `api_overview`
- `api_sentiment_timeseries`
- `api_sentiment_by_channel`
- `api_topics`
- `api_power_words`
- `api_engagement`
- `api_contributors`
- `api_negative_messages`
- `api_positive_messages`
- `api_purpose`
- `api_reddit_comparison`
- `api_raw_messages`
- `api_channels`
- `api_cuebot_engagement_score`
- `api_cuebot_leaderboard`
- `api_cuebot_user_profile`
- `api_cuebot_crossref`

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/app.py
git commit -m "feat(web): prefix all API routes with client_name"
```

### Task 4: Create Layout Template

**Files:**
- Create: `src/dashboard/templates/layout.html`

- [ ] **Step 1: Create `layout.html` with professional sidebar**
Include links to Dashboard, Hub, and a client switcher.

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/templates/layout.html
git commit -m "feat(web): add base layout with professional sidebar"
```

### Task 5: Create Hub Template

**Files:**
- Create: `src/dashboard/templates/hub.html`

- [ ] **Step 1: Create `hub.html` for client selection**
Display clients from `config.yaml` as cards.

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/templates/hub.html
git commit -m "feat(web): add client selection hub template"
```

### Task 6: Update Index Template

**Files:**
- Modify: `src/dashboard/templates/index.html`

- [ ] **Step 1: Update `index.html` to extend `layout.html`**
Remove redundant styles and structure. Update API calls to use `client_name`.

- [ ] **Step 2: Commit**

```bash
git add src/dashboard/templates/index.html
git commit -m "feat(web): refactor index template to use new layout and dynamic routing"
```
