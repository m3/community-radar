# Task 2 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `abort` import to top-level and harden `api_queue_retry` with `try...except` and JSON error responses.

**Architecture:** Refactor `src/dashboard/app.py` for cleaner imports and more resilient API endpoints.

**Tech Stack:** Python, Flask, SQLite.

---

### Task 1: Refactor Flask Imports

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Move `abort` to top-level imports**
- [ ] **Step 2: Remove local `abort` import in `validate_client`**

```python
# Change 1: Top of file
from flask import Flask, render_template, jsonify, request, current_app, abort

# Change 2: Inside validate_client
def validate_client(client_name):
    config = load_config()
    if client_name not in config.get("clients", {}):
        abort(404)
```

### Task 2: Harden `api_queue_retry`

**Files:**
- Modify: `src/dashboard/app.py`
- Test: `tests/test_api_queue.py`

- [ ] **Step 1: Create API test for retry**
- [ ] **Step 2: Implement `try...except` in `api_queue_retry`**

```python
@app.route("/api/queue/retry/<int:task_id>", methods=["POST"])
def api_queue_retry(task_id):
    try:
        from src.db.queue import get_queue_db
        db = get_queue_db()
        db.execute("UPDATE tasks SET status='pending', error_log=NULL, started_at=NULL, finished_at=NULL WHERE id=?", (task_id,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
```

- [ ] **Step 3: Verify with tests**

### Task 3: Commit Changes

- [ ] **Step 1: Commit**
