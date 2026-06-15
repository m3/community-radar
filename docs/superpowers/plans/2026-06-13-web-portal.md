# Multi-Tenant Web Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the basic dashboard into a professional Multi-Tenant Web Portal with dynamic routing, real-time queue monitoring, and client management.

**Architecture:** 
- **Dynamic Routing:** URL-based multi-tenancy (`/<client_name>/dashboard`).
- **Sidebar Navigation:** Persistent layout with client switcher and navigation links.
- **Queue Monitor:** Visual real-time view of `data/queue.db`.
- **Actionable UI:** Trigger analysis/collection tasks directly from the browser.

**Tech Stack:** Python, Flask, Jinja2, Chart.js, SQLite.

---

### Task 1: Dynamic Tenant Routing & Client Hub

**Files:**
- Modify: `src/dashboard/app.py`
- Create: `src/dashboard/templates/layout.html`
- Create: `src/dashboard/templates/hub.html`
- Modify: `src/dashboard/templates/index.html`

- [ ] **Step 1: Refactor `app.py` for dynamic client routing**

Remove `current_app.config.get('CLIENT_NAME')` logic in favor of function-parameter based tenancy.

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
    # Validate client exists
    config = load_config()
    if client_name not in config.get("clients", {}):
        abort(404)
        
    # Use context or local variable instead of app.config for thread-safety
    report = load_report_scoped(client_name)
    return render_template("index.html", client_name=client_name, report=report)

# Refactor all /api routes to take <client_name> as a prefix
# e.g., @app.route("/api/<client_name>/overview")
```

- [ ] **Step 2: Create a base `layout.html` with sidebar**

Include a searchable client dropdown and links to Dashboard, Queue, and Clients.

- [ ] **Step 3: Create `hub.html` for client selection**

- [ ] **Step 4: Update `index.html` to extend `layout.html`**

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/
git commit -m "feat(web): add dynamic client routing and navigation layout"
```

---

### Task 2: Real-time Queue Monitor UI

**Files:**
- Modify: `src/dashboard/app.py`
- Create: `src/dashboard/templates/queue.html`

- [ ] **Step 1: Add `/queue` routes to `app.py`**

```python
@app.route("/queue")
def queue_view():
    return render_template("queue.html")

@app.route("/api/queue/status")
def api_queue_status():
    from src.db.queue import get_queue_db
    db = get_queue_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 50").fetchall()
    db.close()
    return jsonify([dict(t) for t in tasks])

@app.route("/api/queue/retry/<int:task_id>", methods=["POST"])
def api_queue_retry(task_id):
    # Logic from main.py queue retry
    pass
```

- [ ] **Step 2: Create `queue.html` with auto-refreshing table**

Use `setInterval` to fetch `/api/queue/status` every 5 seconds. Add "Retry" buttons for failed tasks.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/
git commit -m "feat(web): add real-time queue monitoring UI"
```

---

### Task 3: Interactive Task Triggers

**Files:**
- Modify: `src/dashboard/app.py`
- Modify: `src/dashboard/templates/index.html`

- [ ] **Step 1: Add task enqueuing API**

```python
@app.route("/api/<client_name>/trigger/<command>", methods=["POST"])
def api_trigger_task(client_name, command):
    if command not in ["collect", "analyze", "report"]:
        return jsonify({"success": False, "error": "Invalid command"}), 400
        
    from src.db.queue import enqueue_task
    # Enqueue with standard args
    enqueue_task(client_name, command, {"client": client_name})
    return jsonify({"success": True})
```

- [ ] **Step 2: Add "Refresh Intel" button to dashboard**

Add a button to the client dashboard that calls the trigger API and shows a toast notification.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/
git commit -m "feat(web): support triggering background tasks from UI"
```

---

### Task 4: Client Onboarding & Config Editor (Read-Only first)

**Files:**
- Modify: `src/dashboard/app.py`
- Create: `src/dashboard/templates/clients.html`

- [ ] **Step 1: Create `/clients` view to show current configs**

Show subreddits, domains, and discord servers for each client in a clean UI card format.

- [ ] **Step 2: Add "Add Client" placeholder form**

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/
git commit -m "feat(web): add client management overview"
```
