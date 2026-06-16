# Heuristic Identity Engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `match_identities` function to identify potential cross-platform identity matches between Discord and Reddit users based on exact and fuzzy username matching.

**Architecture:** The function will process a list of user dictionaries, separating them by platform (Discord/Reddit) based on ID prefix. It will then perform exact matches and fuzzy matches (using `rapidfuzz` or `difflib`) to generate a list of cross-reference records.

**Tech Stack:** Python, `rapidfuzz` (if available) or `difflib` (standard library).

---

### Task 1: Scaffolding and Initial Test

**Files:**
- Create: `src/analysis/identity.py`
- Create: `tests/test_identity_engine.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from src.analysis.identity import match_identities

def test_match_identities_exact():
    users = [
        {"id": "123", "username": "JohnDoe", "display_name": "John"},
        {"id": "reddit_JohnDoe", "username": "JohnDoe", "display_name": "JD"}
    ]
    matches = match_identities(users)
    assert len(matches) == 1
    assert matches[0]["match_type"] == "exact"
    assert matches[0]["confidence"] == 1.0
    assert matches[0]["user_id"] == "123"
    assert matches[0]["username1"] == "JohnDoe"
    assert matches[0]["platform1"] == "discord"
    assert matches[0]["username2"] == "JohnDoe"
    assert matches[0]["platform2"] == "reddit"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_engine.py -v`
Expected: FAIL (Module not found or function not defined)

- [ ] **Step 3: Write minimal implementation**

```python
def match_identities(users):
    discord_users = [u for u in users if not u["id"].startswith("reddit_")]
    reddit_users = [u for u in users if u["id"].startswith("reddit_")]
    
    matches = []
    for d_user in discord_users:
        for r_user in reddit_users:
            if d_user["username"].lower() == r_user["username"].lower():
                matches.append({
                    "user_id": d_user["id"],
                    "platform1": "discord",
                    "username1": d_user["username"],
                    "platform2": "reddit",
                    "username2": r_user["username"],
                    "match_type": "exact",
                    "confidence": 1.0
                })
    return matches
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_identity_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/identity.py tests/test_identity_engine.py
git commit -m "test: initial exact match test and implementation"
```

---

### Task 2: Fuzzy Matching Implementation

**Files:**
- Modify: `src/analysis/identity.py`
- Modify: `tests/test_identity_engine.py`

- [ ] **Step 1: Write failing test for fuzzy matching**

```python
def test_match_identities_fuzzy():
    users = [
        {"id": "456", "username": "JaneDoe", "display_name": "Jane"},
        {"id": "reddit_Jane_Doe", "username": "Jane_Doe", "display_name": "JaneD"}
    ]
    matches = match_identities(users)
    assert len(matches) == 1
    assert matches[0]["match_type"] == "fuzzy"
    assert matches[0]["confidence"] > 0.85
    assert matches[0]["user_id"] == "456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_engine.py::test_match_identities_fuzzy -v`
Expected: FAIL (No match found)

- [ ] **Step 3: Implement fuzzy matching logic**

```python
try:
    from rapidfuzz import fuzz
except ImportError:
    import difflib
    class fuzz:
        @staticmethod
        def ratio(s1, s2):
            return difflib.SequenceMatcher(None, s1, s2).ratio() * 100

def match_identities(users):
    discord_users = [u for u in users if not u["id"].startswith("reddit_")]
    reddit_users = [u for u in users if u["id"].startswith("reddit_")]
    
    matches = []
    for d_user in discord_users:
        d_name = d_user["username"].lower()
        for r_user in reddit_users:
            r_name = r_user["username"].lower()
            
            if d_name == r_name:
                matches.append({
                    "user_id": d_user["id"],
                    "platform1": "discord",
                    "username1": d_user["username"],
                    "platform2": "reddit",
                    "username2": r_user["username"],
                    "match_type": "exact",
                    "confidence": 1.0
                })
                continue
            
            score = fuzz.ratio(d_name, r_name)
            if score > 85:
                matches.append({
                    "user_id": d_user["id"],
                    "platform1": "discord",
                    "username1": d_user["username"],
                    "platform2": "reddit",
                    "username2": r_user["username"],
                    "match_type": "fuzzy",
                    "confidence": score / 100.0
                })
    return matches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_identity_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/identity.py tests/test_identity_engine.py
git commit -m "feat(analysis): implement fuzzy identity matching"
```

---

### Task 3: Final Polish and Validation

**Files:**
- Modify: `src/analysis/identity.py`

- [ ] **Step 1: Ensure documentation and clean exports**

- [ ] **Step 2: Final test run including all project tests**

Run: `pytest`
Expected: ALL PASS

- [ ] **Step 3: Final Commit**

```bash
git add src/analysis/identity.py
git commit -m "feat(analysis): implement heuristic identity matching core"
```
