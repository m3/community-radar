# Client Onboarding & Config Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a form-based UI for managing client configurations in the Web Portal, persisting changes directly to `config.yaml`.

**Architecture:** Use a `ConfigManager` for atomic YAML operations. Flask endpoints will handle CRUD operations for client blocks. The UI will use dynamic JS forms for list management.

**Tech Stack:** Python, Flask, PyYAML, JavaScript, TailwindCSS (for styling).

---

### Task 1: Implement `ConfigManager` for Atomic YAML Updates

**Files:**
- Create: `src/dashboard/config_manager.py`
- Test: `tests/test_config_manager.py`

- [ ] **Step 1: Write failing test for YAML round-tripping**

```python
import pytest
from pathlib import Path
from src.dashboard.config_manager import ConfigManager

def test_yaml_round_trip(tmp_path):
    config_path = tmp_path / "config.yaml"
    initial_content = "clients:\n  test-client:\n    name: Test Client\n"
    config_path.write_text(initial_content)
    
    cm = ConfigManager(config_path)
    config = cm.load()
    config['clients']['test-client']['name'] = 'Updated Name'
    cm.save(config)
    
    updated_content = config_path.read_text()
    assert "name: Updated Name" in updated_content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_config_manager.py -v`
Expected: FAIL (Module not found)

- [ ] **Step 3: Implement `ConfigManager` with atomic writes**

```python
import yaml
import os
import shutil
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.backup_path = self.config_path.with_suffix('.yaml.bak')

    def load(self):
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f) or {}

    def save(self, config_dict):
        # Create backup if not exists
        if not self.backup_path.exists():
            shutil.copy(self.config_path, self.backup_path)
            
        tmp_path = self.config_path.with_suffix('.yaml.tmp')
        with open(tmp_path, 'w') as f:
            yaml.dump(config_dict, f, sort_keys=False, default_flow_style=False)
        
        # Atomic rename
        os.replace(tmp_path, self.config_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_config_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dashboard/config_manager.py tests/test_config_manager.py
git commit -m "feat(dashboard): implement ConfigManager for atomic YAML updates"
```

---

### Task 2: Implement Client Management API Endpoints

**Files:**
- Modify: `src/dashboard/app.py`
- Test: `tests/test_client_api.py`

- [ ] **Step 1: Write failing tests for Client API**

```python
import pytest
import json
from src.dashboard.app import app

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
```

- [ ] **Step 2: Add API routes to `app.py`**

```python
from src.dashboard.config_manager import ConfigManager
config_mgr = ConfigManager(ROOT / "config.yaml")

@app.route("/api/clients")
def api_get_clients():
    config = config_mgr.load()
    return jsonify({"clients": config.get("clients", {})})

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
    return jsonify({"success": True})

@app.route("/api/clients/<client_name>/update", methods=["POST"])
def api_update_client_config(client_name):
    validate_client(client_name)
    new_client_config = request.json
    
    config = config_mgr.load()
    config["clients"][client_name] = new_client_config
    config_mgr.save(config)
    return jsonify({"success": True})
```

- [ ] **Step 3: Run tests and verify**

Run: `PYTHONPATH=. uv run pytest tests/test_client_api.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/dashboard/app.py
git commit -m "feat(dashboard): add API endpoints for client management"
```

---

### Task 3: Create Client Hub UI

**Files:**
- Create: `src/dashboard/templates/clients.html`
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Add `/clients` route to `app.py`**

```python
@app.route("/clients")
def clients_hub():
    """Client management overview."""
    return render_template("clients.html")
```

- [ ] **Step 2: Implement `clients.html` with grid and "Add Client" modal**

Use Tailwind for card styling. Fetch clients via `/api/clients`.

- [ ] **Step 3: Commit**

```bash
git add src/dashboard/templates/clients.html src/dashboard/app.py
git commit -m "feat(web): add client hub UI"
```

---

### Task 4: Implement Form-Based Config Editor

**Files:**
- Create: `src/dashboard/templates/client_edit.html`
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Add `/clients/<client_id>/edit` route to `app.py`**

```python
@app.route("/clients/<client_name>/edit")
def client_edit(client_name):
    validate_client(client_name)
    config = config_mgr.load()
    client_config = config["clients"][client_name]
    return render_template("client_edit.html", client_name=client_name, config=client_config)
```

- [ ] **Step 2: Implement `client_edit.html` with tabbed form and dynamic lists**

Include JS functions to add/remove subreddit and keyword inputs.

- [ ] **Step 3: Verify and Commit**

```bash
git add src/dashboard/templates/client_edit.html src/dashboard/app.py
git commit -m "feat(web): implement form-based configuration editor"
```
