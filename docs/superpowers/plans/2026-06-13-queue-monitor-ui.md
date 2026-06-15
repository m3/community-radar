# Real-time Queue Monitor UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a real-time web UI to monitor and manage the background task queue.

**Architecture:** Add Flask routes to `app.py` to serve a global `/queue` page and API endpoints. Create `queue.html` with vanilla JS for polling and dynamic updates.

**Tech Stack:** Python, Flask, SQLite, Tailwind CSS, Vanilla JavaScript.

---

### Task 1: Backend Routes

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Add `/queue` and API routes to `app.py`**

Add the following routes to `src/dashboard/app.py`:

```python
@app.route("/queue")
def queue_view():
    return render_template("queue.html", client_name=None)

@app.route("/api/queue/status")
def api_queue_status():
    from src.db.queue import get_queue_db
    db = get_queue_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY id DESC LIMIT 50").fetchall()
    db.close()
    return jsonify([dict(t) for t in tasks])

@app.route("/api/queue/retry/<int:task_id>", methods=["POST"])
def api_queue_retry(task_id):
    from src.db.queue import get_queue_db
    db = get_queue_db()
    db.execute("UPDATE tasks SET status='pending', error_log=NULL, started_at=NULL, finished_at=NULL WHERE id=?", (task_id,))
    db.commit()
    db.close()
    return jsonify({"success": True})
```

- [ ] **Step 2: Commit backend changes**

```bash
git add src/dashboard/app.py
git commit -m "feat(web): add backend routes for queue monitor"
```

### Task 2: Frontend Template

**Files:**
- Create: `src/dashboard/templates/queue.html`
- Modify: `src/dashboard/templates/layout.html`

- [ ] **Step 1: Create `src/dashboard/templates/queue.html`**

```html
{% extends "layout.html" %}

{% block title %}Execution Queue - CommunityRadar{% endblock %}

{% block content %}
<div class="space-y-6">
    <div class="flex items-center justify-between">
        <h1 class="text-3xl font-bold text-white neon-glow">Execution Queue</h1>
        <div class="flex items-center space-x-2 text-sm text-slate-400">
            <span id="last-updated">Updating...</span>
            <div id="loading-spinner" class="w-4 h-4 border-2 border-sky-500 border-t-transparent rounded-full animate-spin hidden"></div>
        </div>
    </div>

    <div class="radar-card overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-slate-800/50 border-b border-slate-700">
                        <th class="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">ID</th>
                        <th class="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Client</th>
                        <th class="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Command</th>
                        <th class="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                        <th class="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Created At</th>
                        <th class="px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider text-right">Actions</th>
                    </tr>
                </thead>
                <tbody id="queue-table-body">
                    <!-- Tasks will be injected here -->
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<script>
    async function fetchQueueStatus() {
        const spinner = document.getElementById('loading-spinner');
        spinner.classList.remove('hidden');
        
        try {
            const response = await fetch('/api/queue/status');
            const tasks = await response.json();
            renderTasks(tasks);
            document.getElementById('last-updated').textContent = 'Last updated: ' + new Date().toLocaleTimeString();
        } catch (error) {
            console.error('Error fetching queue status:', error);
        } finally {
            spinner.classList.add('hidden');
        }
    }

    function renderTasks(tasks) {
        const tbody = document.getElementById('queue-table-body');
        tbody.innerHTML = tasks.map(task => `
            <tr class="border-b border-slate-700/50 hover:bg-slate-800/30 transition-colors">
                <td class="px-6 py-4 text-sm text-slate-300">#${task.id}</td>
                <td class="px-6 py-4 text-sm text-sky-400 font-medium">${task.client_name || 'System'}</td>
                <td class="px-6 py-4 text-sm font-mono text-slate-300">
                    <span class="bg-slate-900 px-2 py-1 rounded border border-slate-700">${task.command}</span>
                </td>
                <td class="px-6 py-4">
                    <span class="px-2 py-1 text-xs font-bold rounded-full ${getStatusClass(task.status)}">
                        ${task.status.toUpperCase()}
                    </span>
                </td>
                <td class="px-6 py-4 text-sm text-slate-400">${task.created_at}</td>
                <td class="px-6 py-4 text-right">
                    <button onclick="retryTask(${task.id})" class="text-slate-400 hover:text-sky-400 transition-colors" title="Retry Task">
                        <i class="fas fa-redo-alt"></i>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    function getStatusClass(status) {
        switch (status) {
            case 'pending': return 'bg-yellow-500/20 text-yellow-500';
            case 'running': return 'bg-blue-500/20 text-blue-500 animate-pulse';
            case 'completed': return 'bg-green-500/20 text-green-500';
            case 'failed': return 'bg-red-500/20 text-red-500';
            default: return 'bg-slate-500/20 text-slate-500';
        }
    }

    async function retryTask(taskId) {
        if (!confirm('Are you sure you want to retry task #' + taskId + '?')) return;
        
        try {
            const response = await fetch('/api/queue/retry/' + taskId, { method: 'POST' });
            if (response.ok) {
                fetchQueueStatus();
            }
        } catch (error) {
            console.error('Error retrying task:', error);
        }
    }

    // Initial fetch
    fetchQueueStatus();
    // Poll every 5 seconds
    setInterval(fetchQueueStatus, 5000);
</script>
{% endblock %}
```

- [ ] **Step 2: Update `layout.html` to link to `/queue`**

Update the "Execution Queue" link in `src/dashboard/templates/layout.html`:

```html
            <a href="/queue" class="nav-link flex items-center px-4 py-3 text-sm font-medium rounded-lg {% if request.path == '/queue' %}active{% endif %}">
                <i class="fas fa-tasks w-6"></i>
                Execution Queue
            </a>
```

- [ ] **Step 3: Commit frontend changes**

```bash
git add src/dashboard/templates/queue.html src/dashboard/templates/layout.html
git commit -m "feat(web): add real-time queue monitor UI"
```
