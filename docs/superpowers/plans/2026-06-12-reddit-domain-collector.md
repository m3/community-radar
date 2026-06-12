# Reddit Domain Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a script to collect posts from specific domains on Reddit using the Chrome bridge and store them in the database.

**Architecture:** Extend the existing domain URL builder into a full collector script. Follow the pattern in `src/collectors/reddit.py` but use domain-specific logic.

**Tech Stack:** Python, SQLite, reddit-skills (Chrome bridge).

---

### Task 1: Complete src/collectors/reddit_domain.py Structure

**Files:**
- Modify: `src/collectors/reddit_domain.py`

- [ ] **Step 1: Add imports and configuration loading**

```python
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import yaml
from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

# Load config
CONFIG_PATH = Path("/Users/mathias/Development/Projects/community-radar/config.yaml")
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

REDDIT_SKILLS_DIR = Path(CONFIG["reddit"]["skills_dir"])
DATA_DIR = Path("/Users/mathias/Development/Projects/community-radar/data")
DOMAINS = CONFIG["reddit"].get("domain_monitoring", [])
```

- [ ] **Step 2: Add run_cli helper (copied from reddit.py)**

```python
def run_cli(args, timeout=60):
    """Run reddit-skills CLI and return parsed output"""
    import subprocess
    full_args = [
        "uv", "run",
        "--directory", str(REDDIT_SKILLS_DIR),
        "python", "cli.py",
    ] + args

    result = subprocess.run(full_args, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        print(f"  ✗ reddit-skills error: {result.stderr[:200]}")
        return None

    try:
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except json.JSONDecodeError:
        print(f"  ⚠ Could not parse output: {result.stdout[:200]}")
        return None
```

- [ ] **Step 3: Commit structural changes**

```bash
git add src/collectors/reddit_domain.py
git commit -m "feat(reddit): add structure and imports to domain collector"
```

### Task 2: Implement Fetching Logic

**Files:**
- Modify: `src/collectors/reddit_domain.py`

- [ ] **Step 1: Implement fetch_domain_posts_via_json**

```python
def fetch_domain_posts_via_json(domain, sort="new", limit=100, max_pages=3):
    """Fetch posts for a domain using the Chrome bridge CLI."""
    all_posts = []
    after = ""

    for page_num in range(max_pages):
        # Build the .json URL for the domain
        # Note: reddit-skills json-feed might need update to support domain URLs,
        # but the plan says to use building URL logic.
        # For now, we use a generic command if available or adapt.
        # Actually, let's use the 'json-feed' command but pass domain URL if it supports it.
        # If it doesn't, we'll need Task 3 to fix it.
        
        result = run_cli([
            "json-feed",
            "--url", build_domain_json_url(domain, sort, limit, after if after else None),
        ], timeout=30)

        if not result:
            print(f"  ✗ No response from json-feed at page {page_num + 1}")
            break

        posts = result.get("posts", [])
        if not posts:
            print(f"  No more posts at page {page_num + 1}")
            break

        all_posts.extend(posts)
        after = result.get("after", "")
        if not after:
            break

        print(f"  Page {page_num + 1}: {len(posts)} posts (total: {len(all_posts)})")
        time.sleep(1)

    return all_posts
```

- [ ] **Step 2: Commit fetching logic**

```bash
git add src/collectors/reddit_domain.py
git commit -m "feat(reddit): implement domain post fetching"
```

### Task 3: Implement Storage Logic

**Files:**
- Modify: `src/collectors/reddit_domain.py`

- [ ] **Step 1: Implement export_domain**

```python
def export_domain(domain, sort="new", max_pages=3):
    """Fetch and store domain posts in DB."""
    print(f"  📥 domain/{domain} ({sort})...")
    posts = fetch_domain_posts_via_json(domain, sort, limit=100, max_pages=max_pages)
    
    if not posts:
        print(f"  ✗ No posts fetched")
        return 0

    db = get_db()
    server_id = "reddit_domain_monitoring"
    upsert_server(db, server_id, "Reddit Domain Monitoring")

    channel_id = f"domain:{domain}"
    upsert_channel(db, channel_id, server_id, f"domain:{domain}")

    # Upsert placeholder deleted user
    upsert_user(db, "reddit_[deleted]", display_name="[deleted]", username="[deleted]", role="reddit_user")

    new_users = 0
    msg_count = 0
    for post in posts:
        author = post.get("author", {}).get("name", "[deleted]")
        uid = f"reddit_{author}" if author != "[deleted]" else "reddit_[deleted]"
        if author != "[deleted]":
            if upsert_user(db, uid, display_name=author, username=author, role="reddit_user") == "new":
                new_users += 1
        
        created_utc = post.get("createdUtc", 0)
        created_date = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if created_utc else None
        
        content = f"{post['title']}\n\n{post.get('selftext', '')}" if post.get('selftext') else post['title']
        content += f"\n\nURL: {post.get('url', '')}"
        
        db.execute("""
            INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reactions, platform)
            VALUES (?, ?, ?, ?, ?, ?, 'reddit')
        """, (
            post["id"], channel_id, uid, content, created_date, post["stats"]["score"]
        ))
        msg_count += 1

    db.execute("UPDATE channels SET message_count=?, last_scan=datetime('now') WHERE id=?", (msg_count, channel_id))
    db.commit()
    db.close()
    
    print(f"  ✅ {msg_count} messages, {new_users} new users")
    return msg_count
```

- [ ] **Step 2: Commit storage logic**

```bash
git add src/collectors/reddit_domain.py
git commit -m "feat(reddit): implement domain post storage"
```

### Task 4: Implement Main Execution Loop

**Files:**
- Modify: `src/collectors/reddit_domain.py`

- [ ] **Step 1: Add export_all_domains and __main__**

```python
def export_all_domains():
    total_msgs = 0
    for domain in DOMAINS:
        total_msgs += export_domain(domain)
    print(f"\n✅ Total Domain Messages: {total_msgs}")

if __name__ == "__main__":
    export_all_domains()
```

- [ ] **Step 2: Commit final script**

```bash
git add src/collectors/reddit_domain.py
git commit -m "feat(reddit): add domain collection main loop"
```
