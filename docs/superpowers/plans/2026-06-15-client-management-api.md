# Client Management API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Client Management API endpoints in `src/dashboard/app.py` using `ConfigManager`.

**Architecture:** Add Flask routes to `src/dashboard/app.py`. Use `ConfigManager` for persistence. Ensure `load_config` cache is cleared on updates.

**Tech Stack:** Flask, Pytest, YAML

---

### Task 1: Setup Failing Tests

**Files:**
- Create: `tests/test_client_api.py`

- [ ] **Step 1: Write initial failing tests**

```python
import pytest
import json
from src.dashboard.app import app
import os
from pathlib import Path

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_clients(client):
    response = client.get('/api/clients')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'clients' in data

def test_create_client(client):
    payload = {
        "client_id": "test_client",
        "name": "Test Client"
    }
    response = client.post('/api/clients', json=payload)
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True

def test_update_client(client):
    # First create
    client.post('/api/clients', json={"client_id": "upd_client", "name": "Old Name"})
    
    # Then update
    payload = {
        "name": "New Name",
        "reddit": {"subreddits": ["test"]},
        "discord": {"servers": ["123"]}
    }
    response = client.post('/api/clients/upd_client/update', json=payload)
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True
    
    # Verify update
    get_resp = client.get('/api/clients')
    data = json.loads(get_resp.data)
    assert data["clients"]["upd_client"]["name"] == "New Name"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. uv run pytest tests/test_client_api.py -v`
Expected: FAIL (404 for all endpoints)

---

### Task 2: Implement API Endpoints

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Import ConfigManager and initialize**

```python
from src.dashboard.config_manager import ConfigManager
config_mgr = ConfigManager(ROOT / "config.yaml")
```

- [ ] **Step 2: Implement GET /api/clients**

```python
@app.route("/api/clients")
def api_get_clients():
    config = config_mgr.load()
    return jsonify({"clients": config.get("clients", {})})
```

- [ ] **Step 3: Implement POST /api/clients**

```python
@app.route("/api/clients", methods=["POST"])
def api_create_client():
    data = request.json
    client_id = data.get("client_id")
    name = data.get("name")
    
    if not client_id or not client_id.isalnum():
        return jsonify({"success": False, "error": "Invalid client_id"}), 400
        
    config = config_mgr.load()
    if client_id in config.get("clients", {}):
        return jsonify({"success": False, "error": "Client already exists"}), 400
        
    config.setdefault("clients", {})[client_id] = {
        "name": name,
        "reddit": {"subreddits": {}},
        "discord": {"servers": {}}
    }
    config_mgr.save(config)
    load_config.cache_clear()
    return jsonify({"success": True})
```

- [ ] **Step 4: Implement POST /api/clients/<client_name>/update**

```python
@app.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    validate_client(client_name)
    new_client_config = request.json
    
    config = config_mgr.load()
    config["clients"][client_name] = new_client_config
    config_mgr.save(config)
    load_config.cache_clear()
    return jsonify({"success": True})
```

---

### Task 3: Verify and Commit

- [ ] **Step 1: Run tests to verify they pass**

Run: `PYTHONPATH=. uv run pytest tests/test_client_api.py -v`
Expected: PASS

- [ ] **Step 2: Commit changes**

```bash
git add src/dashboard/app.py tests/test_client_api.py
git commit -m "feat(dashboard): add API endpoints for client management"
```
