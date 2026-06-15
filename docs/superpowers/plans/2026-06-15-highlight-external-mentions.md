# Highlight External Mentions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `api_raw_messages` endpoint in `src/dashboard/app.py` to flag "External Mentions" based on client configuration.

**Architecture:** Post-processing message rows in Python after database retrieval to add `is_external_mention` boolean flag based on subreddit prefixes and track keywords.

**Tech Stack:** Python, Flask, SQLite.

---

### Task 1: Create Test for External Mentions Flagging

**Files:**
- Create: `tests/test_raw_messages_enrichment.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import json
from src.dashboard.app import app, config_mgr
import yaml
from unittest.mock import MagicMock, patch

@pytest.fixture
def client(tmp_path):
    app.config['TESTING'] = True
    temp_config = tmp_path / "config.yaml"
    initial_config = {
        "clients": {
            "test-client": {
                "name": "Test Client",
                "reddit": {
                    "subreddits": {
                        "billiards": {
                            "track_keywords": ["pure pool", "snooker"]
                        }
                    }
                }
            }
        }
    }
    with open(temp_config, "w") as f:
        yaml.dump(initial_config, f)
    
    old_path = config_mgr.config_path
    config_mgr.config_path = temp_config
    config_mgr.clear_cache()
    
    with app.test_client() as client:
        yield client
        
    config_mgr.config_path = old_path
    config_mgr.clear_cache()

def test_api_raw_messages_flags_external_mention(client):
    # Mock DB response
    mock_db = MagicMock()
    mock_row_external = {
        "message_id": "1",
        "content": "I love playing pure pool on my PC",
        "channel_name": "reddit_billiards",
        "platform": "reddit",
        "timestamp": "2023-01-01T00:00:00",
        "display_name": "user1",
        "reactions": None,
        "channel_id": 1,
        "reply_to": None,
        "role": None
    }
    mock_row_normal = {
        "message_id": "2",
        "content": "Hello world",
        "channel_name": "general",
        "platform": "discord",
        "timestamp": "2023-01-01T00:00:01",
        "display_name": "user2",
        "reactions": None,
        "channel_id": 2,
        "reply_to": None,
        "role": None
    }
    
    class MockRow(dict):
        pass

    mock_db.execute.return_value.fetchall.return_value = [MockRow(mock_row_external), MockRow(mock_row_normal)]
    
    with patch('src.dashboard.app.get_db', return_value=mock_db):
        response = client.get('/api/test-client/raw_messages')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data[0]["message_id"] == "1"
        assert data[0]["is_external_mention"] is True
        
        assert data[1]["message_id"] == "2"
        assert data[1]["is_external_mention"] is False

def test_api_raw_messages_no_keywords_no_flag(client):
    # Mock DB response
    mock_db = MagicMock()
    mock_row = {
        "message_id": "3",
        "content": "just some random text",
        "channel_name": "reddit_billiards",
        "platform": "reddit",
        "timestamp": "2023-01-01T00:00:02",
        "display_name": "user3",
        "reactions": None,
        "channel_id": 1,
        "reply_to": None,
        "role": None
    }
    
    class MockRow(dict):
        pass

    mock_db.execute.return_value.fetchall.return_value = [MockRow(mock_row)]
    
    with patch('src.dashboard.app.get_db', return_value=mock_db):
        response = client.get('/api/test-client/raw_messages')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data[0]["is_external_mention"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_raw_messages_enrichment.py -v`
Expected: FAIL (KeyError: 'is_external_mention')

- [ ] **Step 3: Commit test**

```bash
git add tests/test_raw_messages_enrichment.py
git commit -m "test: add test for external mentions flagging"
```

---

### Task 2: Implement Flagging Logic in `app.py`

**Files:**
- Modify: `src/dashboard/app.py`

- [ ] **Step 1: Update `api_raw_messages` implementation**

```python
@app.route("/api/<client_name>/raw_messages")
def api_raw_messages(client_name):
    """Raw messages for detailed view with filters."""
    validate_client(client_name)
    db = get_db(client_name)

    platform = request.args.get("platform")
    channel = request.args.get("channel")
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    query = """
        SELECT m.message_id, m.content, m.timestamp, m.reactions, m.channel_id,
               m.platform, m.reply_to,
               c.name as channel_name,
               u.display_name, u.role
        FROM messages m
        JOIN channels c ON m.channel_id = c.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.content IS NOT NULL AND m.content != ''
    """
    params = []

    if platform:
        query += " AND m.platform = ?"
        params.append(platform)
    if channel:
        query += " AND c.name = ?"
        params.append(channel)

    query += " ORDER BY m.timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = db.execute(query, params).fetchall()
    db.close()

    # Flag External Mentions
    config = config_mgr.load()
    client_config = config.get("clients", {}).get(client_name, {})
    keywords = []
    external_prefixes = []
    subreddits_config = client_config.get("reddit", {}).get("subreddits", {})
    for sub, sub_conf in subreddits_config.items():
        if "track_keywords" in sub_conf and sub_conf["track_keywords"]:
            keywords.extend(sub_conf["track_keywords"])
            external_prefixes.append(f"reddit_{sub.lower()}")
            
    keywords = list(set([k.lower() for k in keywords]))
    
    result_rows = []
    for r in rows:
        r_dict = dict(r)
        r_dict["is_external_mention"] = False
        
        channel_name = (r_dict.get("channel_name") or "").lower()
        if any(channel_name.startswith(p) for p in external_prefixes):
            content_lower = (r_dict.get("content") or "").lower()
            if any(kw in content_lower for kw in keywords):
                r_dict["is_external_mention"] = True
                
        result_rows.append(r_dict)

    return jsonify(result_rows)
```

- [ ] **Step 2: Run tests to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_raw_messages_enrichment.py -v`
Expected: PASS

- [ ] **Step 3: Commit implementation**

```bash
git add src/dashboard/app.py
git commit -m "feat(api): flag external mentions in raw messages feed"
```
