"""
Reddit collector v3 — uses reddit-skills Chrome bridge for all data.
Now with proper timestamps from <time datetime> attributes.
Stores posts + comments in the database with real timestamps.
"""

import subprocess
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import yaml

from src.db.models import get_db, upsert_server, upsert_channel, upsert_user, log_export

# Load config
CONFIG_PATH = Path("/Users/mathias/Development/community-radar/config.yaml")
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

REDDIT_SKILLS_DIR = Path(CONFIG["reddit"]["skills_dir"])
DATA_DIR = Path("/Users/mathias/Development/community-radar/data")
SUBREDDITS = CONFIG["reddit"]["subreddits"]


def run_cli(args, timeout=60):
    """Run reddit-skills CLI and return parsed output"""
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


def export_subreddit(subreddit, sort="new", with_comments=True, comment_limit=10):
    """Export posts + comments from a subreddit using the Chrome bridge"""
    print(f"  📥 r/{subreddit} ({sort})...")

    data = run_cli(["subreddit-feed", "--subreddit", subreddit, "--sort", sort])
    if not data:
        # Retry once for top sort (Reddit loads it differently)
        if sort == "top":
            print(f"  Retrying r/{subreddit} (top)...")
            time.sleep(3)
            data = run_cli(["subreddit-feed", "--subreddit", subreddit, "--sort", sort])
    if not data:
        return 0, 0

    posts = data.get("posts", [])
    if not posts:
        print(f"  ✗ No posts fetched")
        return 0, 0

    print(f"  Got {len(posts)} posts")

    # Fetch comments for posts that have them
    total_comments = 0
    if with_comments:
        posts_with_comments = sorted(posts, key=lambda p: p.get("stats", {}).get("numComments", 0), reverse=True)
        for post in posts_with_comments[:comment_limit]:
            num_comments = post.get("stats", {}).get("numComments", 0)
            if num_comments > 0:
                time.sleep(1)  # Rate limit
                permalink = post.get("permalink", "")
                if permalink:
                    detail = run_cli(["get-post-detail", "--post-url", f"https://www.reddit.com{permalink}"], timeout=30)
                    if detail:
                        comments = detail.get("comments", [])
                        post["comments"] = comments
                        total_comments += len(comments)
                        print(f"    💬 {post['id']}: {len(comments)} comments")

    # Save raw data
    out_dir = DATA_DIR / "reddit-exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{subreddit}-{sort}-full.json"
    with open(out_path, "w") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {out_path.name}")

    # Store in DB
    db = get_db()
    server_id = f"reddit_{subreddit.lower()}"
    upsert_server(db, server_id, f"Reddit r/{subreddit}")

    channel_id = f"reddit_{subreddit.lower()}_{sort}"
    upsert_channel(db, channel_id, server_id, f"reddit-{subreddit}-{sort}")

    new_users = 0
    msg_count = 0

    for post in posts:
        author = post.get("author", {})
        author_name = author.get("name", "unknown") if isinstance(author, dict) else str(author)

        if author_name and author_name != "unknown":
            uid = f"reddit_{author_name}"
            result = upsert_user(db, uid, display_name=author_name, username=author_name, role="reddit_user")
            if result == "new":
                new_users += 1

        # Convert timestamp
        created_utc = post.get("createdUtc", 0)
        if created_utc:
            created_date = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        else:
            created_date = None

        # Insert post as message
        content = f"{post['title']}\n\n{post.get('selftext', '')}" if post.get('selftext') else post['title']
        db.execute("""
            INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reactions, platform)
            VALUES (?, ?, ?, ?, ?, ?, 'reddit')
        """, (
            post["id"],
            channel_id,
            f"reddit_{author_name}",
            content,
            created_date,
            post.get("stats", {}).get("score", 0),
        ))
        msg_count += 1

        # Insert comments as messages
        for comment in post.get("comments", []):
            c_author = comment.get("author", {})
            c_author_name = c_author.get("name", "unknown") if isinstance(c_author, dict) else str(c_author)

            if c_author_name and c_author_name != "unknown":
                uid = f"reddit_{c_author_name}"
                result = upsert_user(db, uid, display_name=c_author_name, username=c_author_name, role="reddit_user")
                if result == "new":
                    new_users += 1

            c_created_utc = comment.get("createdUtc", 0)
            if c_created_utc:
                c_created_date = datetime.fromtimestamp(c_created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            else:
                c_created_date = None

            db.execute("""
                INSERT OR IGNORE INTO messages (message_id, channel_id, user_id, content, timestamp, reply_to, reactions, platform)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'reddit')
            """, (
                comment.get("id", ""),
                channel_id,
                f"reddit_{c_author_name}",
                comment.get("body", ""),
                c_created_date,
                post["id"],
                comment.get("score", 0),
            ))
            msg_count += 1

    # Update channel/server counts
    db.execute("UPDATE channels SET message_count=?, last_scan=datetime('now') WHERE id=?",
               (msg_count, channel_id))
    db.execute("UPDATE servers SET total_messages=total_messages+?, last_scan=datetime('now') WHERE id=?",
               (msg_count, server_id))

    log_export(db, server_id, channel_id, msg_count, new_users, 0, "imported")
    db.commit()
    db.close()

    print(f"  ✅ {msg_count} messages ({total_comments} comments), {new_users} new users")
    return msg_count, total_comments


def export_all():
    """Export all configured subreddits"""
    total_msgs = 0
    total_comments = 0
    for sub, config in SUBREDDITS.items():
        print(f"\n📡 r/{sub}")
        for sort in config["sorts"]:
            msgs, comments = export_subreddit(sub, sort)
            total_msgs += msgs
            total_comments += comments
            time.sleep(2)  # Rate limit between sorts
    print(f"\n✅ Total: {total_msgs} messages ({total_comments} comments)")
    return total_msgs


if __name__ == "__main__":
    export_all()
