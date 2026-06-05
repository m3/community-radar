"""Reddit collector — uses reddit-skills Chrome extension bridge"""

import subprocess
import json
import time
from pathlib import Path

import yaml

from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

# Load config
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

REDDIT_SKILLS_DIR = Path(CONFIG["reddit"]["skills_dir"])
DATA_DIR = Path(__file__).parent.parent.parent / CONFIG.get("data_dir", "data")
SUBREDDITS = CONFIG["reddit"]["subreddits"]


def run_cli(args):
    """Run reddit-skills CLI and return parsed output"""
    full_args = [
        "uv", "run",
        "--directory", str(REDDIT_SKILLS_DIR),
        "python", "scripts/cli.py",
    ] + args

    result = subprocess.run(full_args, capture_output=True, text=True, timeout=60)
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


def export_subreddit(subreddit, sort="top", limit=25):
    """Export posts from a subreddit"""
    print(f"  📥 Fetching r/{subreddit} ({sort})...")

    data = run_cli(["subreddit-feed", "--subreddit", subreddit, "--sort", sort])
    if not data:
        return 0

    posts = data.get("posts", [])
    print(f"  Got {len(posts)} posts")

    db = get_db()
    server_id = f"reddit_{subreddit.lower()}"
    upsert_server(db, server_id, f"Reddit r/{subreddit}")

    for post in posts:
        author = post.get("author", {})
        author_name = author.get("name", "unknown") if isinstance(author, dict) else str(author)

        # Upsert user
        if author_name and author_name != "unknown":
            upsert_user(db, f"reddit_{author_name}",
                        display_name=author_name,
                        username=author_name,
                        role="reddit_user")

    channel_id = f"reddit_{subreddit.lower()}_{sort}"
    upsert_channel(db, channel_id, server_id, f"reddit-{subreddit}-{sort}")

    # Save raw data
    out_dir = DATA_DIR / "reddit-exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{subreddit}-{sort}.json"
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    # Update state
    msg_count = len(posts)
    db.execute("UPDATE channels SET message_count=?, last_scan=datetime('now') WHERE id=?",
               (msg_count, channel_id))
    db.execute("UPDATE servers SET total_messages=total_messages+?, last_scan=datetime('now') WHERE id=?",
               (msg_count, server_id))
    db.execute("UPDATE servers SET total_users=(SELECT COUNT(*) FROM users) WHERE id=?", (server_id,))

    log_export(db, server_id, channel_id, msg_count, 0, 0, "imported")
    db.close()
    return msg_count


def export_all():
    """Export all configured subreddits"""
    total = 0
    for sub, config in SUBREDDITS.items():
        print(f"\n📡 r/{sub}")
        for sort in config["sorts"]:
            count = export_subreddit(sub, sort)
            total += count
    print(f"\n✅ Total: {total} posts exported")
    return total


if __name__ == "__main__":
    export_all()